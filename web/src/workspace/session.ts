import { useCallback, useEffect, useRef, useState } from "react";
import { onAuthStateChanged, signInWithPopup, signOut as firebaseSignOut, type User } from "firebase/auth";
import { newAccount, sortAccounts, type Account, type AccountDraft } from "./accounts";
import { createWorkspace, unlockWorkspace, type WorkspaceHeader, type WorkspaceKey } from "./crypto/vault";
import { googleProvider, type FirebaseServices } from "./firebase";
import { watchInactivity } from "./inactivity";
import { loadAccounts, loadWorkspaceHeader, saveAccount, saveNewWorkspaceHeader } from "./store";

export interface Operator {
  uid: string;
  email: string | null;
  displayName: string | null;
}

export type LockReason = "manual" | "idle";

export type SessionPhase =
  | { kind: "starting" }
  | { kind: "signed-out"; error?: string }
  | { kind: "loading-workspace"; operator: Operator }
  | { kind: "onboarding"; operator: Operator }
  | { kind: "locked"; operator: Operator; header: WorkspaceHeader; reason?: LockReason }
  | { kind: "unlocked"; operator: Operator; header: WorkspaceHeader; accounts: Account[] }
  | { kind: "failed"; operator: Operator; message: string };

export interface WorkspaceSession {
  phase: SessionPhase;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  createWithPassphrase: (passphrase: string) => Promise<void>;
  unlock: (passphrase: string) => Promise<void>;
  lock: (reason?: LockReason) => void;
  addAccount: (draft: AccountDraft) => Promise<Account>;
  retry: () => void;
}

export class SessionEndedError extends Error {
  constructor() {
    super("The workspace was locked before the action finished.");
    this.name = "SessionEndedError";
  }
}

function toOperator(user: User): Operator {
  return { uid: user.uid, email: user.email, displayName: user.displayName };
}

function errorCode(error: unknown): string {
  return typeof error === "object" && error && "code" in error ? String((error as { code: unknown }).code) : "";
}

export function describeError(error: unknown): string {
  const code = errorCode(error);
  if (code === "permission-denied") return "Storage refused the request for this Google account.";
  if (code === "unavailable") return "Cannot reach storage. Check the connection and try again.";
  return error instanceof Error ? error.message : String(error);
}

/**
 * Owns the workspace lifecycle. The decryption key lives in a ref, never in
 * React state, and readable records exist only in the `unlocked` phase, so
 * leaving that phase drops both. An epoch counter stops in-flight work from
 * repopulating readable state after a lock or sign-out.
 */
export function useWorkspaceSession({ auth, db }: FirebaseServices): WorkspaceSession {
  const [phase, setPhase] = useState<SessionPhase>({ kind: "starting" });
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const keyRef = useRef<WorkspaceKey | null>(null);
  const epochRef = useRef(0);
  const operatorRef = useRef<Operator | null>(null);

  const discardKey = useCallback(() => {
    keyRef.current = null;
    epochRef.current += 1;
  }, []);

  const openWorkspace = useCallback(
    async (operator: Operator) => {
      discardKey();
      const epoch = epochRef.current;
      setPhase({ kind: "loading-workspace", operator });
      try {
        const header = await loadWorkspaceHeader(db, operator.uid);
        if (epoch !== epochRef.current) return;
        setPhase(header ? { kind: "locked", operator, header } : { kind: "onboarding", operator });
      } catch (error) {
        if (epoch === epochRef.current) setPhase({ kind: "failed", operator, message: describeError(error) });
      }
    },
    [db, discardKey],
  );

  useEffect(() => {
    let lastUid: string | null | undefined;
    return onAuthStateChanged(auth, (user) => {
      const uid = user?.uid ?? null;
      if (uid === lastUid) return;
      lastUid = uid;
      operatorRef.current = user ? toOperator(user) : null;
      if (user) {
        void openWorkspace(toOperator(user));
      } else {
        discardKey();
        setPhase((current) => (current.kind === "signed-out" ? current : { kind: "signed-out" }));
      }
    });
  }, [auth, discardKey, openWorkspace]);

  const lock = useCallback(
    (reason: LockReason = "manual") => {
      const current = phaseRef.current;
      if (current.kind !== "unlocked") return;
      discardKey();
      setPhase({ kind: "locked", operator: current.operator, header: current.header, reason });
    },
    [discardKey],
  );

  const unlocked = phase.kind === "unlocked";
  useEffect(() => (unlocked ? watchInactivity({ onIdle: () => lock("idle") }) : undefined), [unlocked, lock]);

  const enter = useCallback(
    async (operator: Operator, header: WorkspaceHeader, key: WorkspaceKey, epoch: number) => {
      const accounts = await loadAccounts(db, key);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      keyRef.current = key;
      setPhase({ kind: "unlocked", operator, header, accounts });
    },
    [db],
  );

  const signIn = useCallback(async () => {
    try {
      await signInWithPopup(auth, googleProvider());
    } catch (error) {
      const code = errorCode(error);
      if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") return;
      setPhase({ kind: "signed-out", error: describeError(error) });
    }
  }, [auth]);

  const signOut = useCallback(async () => {
    discardKey();
    setPhase({ kind: "signed-out" });
    // Firestore runs with a memory-only cache, so no workspace data, readable
    // or encrypted, is persisted in the browser. Signing out also removes the
    // persisted Google session.
    await firebaseSignOut(auth);
  }, [auth, discardKey]);

  const createWithPassphrase = useCallback(
    async (passphrase: string) => {
      const current = phaseRef.current;
      if (current.kind !== "onboarding") return;
      const epoch = epochRef.current;
      const { header, workspaceKey } = await createWorkspace(current.operator.uid, passphrase);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      await saveNewWorkspaceHeader(db, current.operator.uid, header);
      await enter(current.operator, header, workspaceKey, epoch);
    },
    [db, enter],
  );

  const unlock = useCallback(
    async (passphrase: string) => {
      const current = phaseRef.current;
      if (current.kind !== "locked") return;
      const epoch = epochRef.current;
      const key = await unlockWorkspace(current.operator.uid, current.header, passphrase);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      await enter(current.operator, current.header, key, epoch);
    },
    [enter],
  );

  const addAccount = useCallback(
    async (draft: AccountDraft) => {
      const key = keyRef.current;
      const epoch = epochRef.current;
      if (!key) throw new SessionEndedError();
      const account = newAccount(draft);
      await saveAccount(db, key, account);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      setPhase((current) => (current.kind === "unlocked" ? { ...current, accounts: sortAccounts([...current.accounts, account]) } : current));
      return account;
    },
    [db],
  );

  const retry = useCallback(() => {
    const operator = operatorRef.current;
    if (operator) void openWorkspace(operator);
    else setPhase({ kind: "signed-out" });
  }, [openWorkspace]);

  return { phase, signIn, signOut, createWithPassphrase, unlock, lock, addAccount, retry };
}
