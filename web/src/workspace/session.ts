import { useCallback, useEffect, useRef, useState } from "react";
import { onAuthStateChanged, signInWithPopup, signOut as firebaseSignOut, type User } from "firebase/auth";
import { newAccount, sortAccounts, type Account, type AccountDraft } from "./accounts";
import {
  operatorEdit,
  rememberChoice,
  rememberedDecisions,
  similarUncategorized,
  undoEdit,
  type Classification,
  type DecisionRecord,
  type MerchantChoice,
} from "./classification/decisions";
import { createWorkspace, unlockWorkspace, type WorkspaceHeader, type WorkspaceKey } from "./crypto/vault";
import { googleProvider, type FirebaseServices } from "./firebase";
import { watchInactivity } from "./inactivity";
import { buildImportBatch, chunkTransactionsOf, sortStatements, sortTransactions, type ImportItem, type StatementImport, type Transaction } from "./import/statements";
import {
  deleteOriginal as deleteStoredOriginal,
  loadAccounts,
  loadImportedHistory,
  loadOriginal as loadStoredOriginal,
  loadWorkspaceHeader,
  saveAccount,
  saveDecisions,
  saveImport,
  saveNewWorkspaceHeader,
} from "./store";

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
  | {
      kind: "unlocked";
      operator: Operator;
      header: WorkspaceHeader;
      accounts: Account[];
      statements: StatementImport[];
      transactions: Transaction[];
      /** Category/type decisions by transaction id. A transaction without one is uncategorized. */
      decisions: ReadonlyMap<string, DecisionRecord>;
      merchantChoices: MerchantChoice[];
    }
  | { kind: "failed"; operator: Operator; message: string };

export interface WorkspaceSession {
  phase: SessionPhase;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  createWithPassphrase: (passphrase: string) => Promise<void>;
  unlock: (passphrase: string) => Promise<void>;
  lock: (reason?: LockReason) => void;
  addAccount: (draft: AccountDraft) => Promise<Account>;
  /** Save confirmed statements in one atomic write. Nothing is stored before this is called. */
  importStatements: (items: ImportItem[]) => Promise<StatementImport[]>;
  loadOriginal: (statementId: string) => Promise<Uint8Array>;
  deleteOriginal: (statementId: string) => Promise<void>;
  /**
   * Set a transaction's category/type. With `remember`, also remember it for
   * the transaction's merchant, for transactions imported later; returns that
   * choice so the operator can explicitly apply it to similar inbox items.
   */
  classify: (transactionId: string, classification: Classification, options?: { remember?: boolean }) => Promise<{ merchantChoice?: MerchantChoice }>;
  /** Resolve the other uncategorized transactions of a remembered choice's merchant. Returns how many were resolved. */
  applyToSimilar: (merchantChoiceId: string) => Promise<number>;
  /** Undo the most recent operator edit of a transaction. */
  undo: (transactionId: string) => Promise<void>;
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
      const [accounts, { decisions, ...history }] = await Promise.all([loadAccounts(db, key), loadImportedHistory(db, key)]);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      keyRef.current = key;
      setPhase({ kind: "unlocked", operator, header, accounts, ...history, decisions: new Map(decisions.map((record) => [record.id, record])) });
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

  const importStatements = useCallback(
    async (items: ImportItem[]) => {
      const key = keyRef.current;
      const epoch = epochRef.current;
      const current = phaseRef.current;
      if (!key || current.kind !== "unlocked") throw new SessionEndedError();
      // Remembered merchant choices classify only these new transactions,
      // never history that already has a decision.
      const plan = await buildImportBatch(items, current.accounts, new Date(), (transactions) =>
        rememberedDecisions(transactions, current.merchantChoices, current.decisions),
      );
      await saveImport(db, key, plan);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      const transactions = plan.transactionChunks.flatMap(chunkTransactionsOf);
      setPhase((latest) => {
        if (latest.kind !== "unlocked") return latest;
        const accounts = new Map(latest.accounts.map((account) => [account.id, account]));
        for (const account of plan.accounts) accounts.set(account.id, account);
        return {
          ...latest,
          accounts: sortAccounts([...accounts.values()]),
          statements: sortStatements([...latest.statements, ...plan.statements]),
          transactions: sortTransactions([...latest.transactions, ...transactions]),
          decisions: withDecisions(latest.decisions, plan.decisions),
        };
      });
      return plan.statements;
    },
    [db],
  );

  const findStatement = (statementId: string) => {
    const key = keyRef.current;
    const current = phaseRef.current;
    if (!key || current.kind !== "unlocked") throw new SessionEndedError();
    const statement = current.statements.find((item) => item.id === statementId);
    if (!statement) throw new Error("That statement is not in this workspace.");
    return { key, statement };
  };

  const loadOriginal = useCallback(
    async (statementId: string) => {
      const { key, statement } = findStatement(statementId);
      const epoch = epochRef.current;
      const bytes = await loadStoredOriginal(db, key, statement);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      return bytes;
    },
    [db],
  );

  const deleteOriginal = useCallback(
    async (statementId: string) => {
      const { key, statement } = findStatement(statementId);
      const epoch = epochRef.current;
      const updated = await deleteStoredOriginal(db, key, statement);
      if (epoch !== epochRef.current) throw new SessionEndedError();
      setPhase((latest) =>
        latest.kind === "unlocked" ? { ...latest, statements: latest.statements.map((item) => (item.id === updated.id ? updated : item)) } : latest,
      );
    },
    [db],
  );

  const unlockedState = () => {
    const key = keyRef.current;
    const current = phaseRef.current;
    if (!key || current.kind !== "unlocked") throw new SessionEndedError();
    return { key, current, epoch: epochRef.current };
  };

  const commitDecisions = useCallback(
    async (key: WorkspaceKey, epoch: number, decisions: DecisionRecord[], merchantChoices: MerchantChoice[] = []) => {
      await saveDecisions(db, key, { decisions, merchantChoices });
      if (epoch !== epochRef.current) throw new SessionEndedError();
      setPhase((latest) => {
        if (latest.kind !== "unlocked") return latest;
        const choices = new Map(latest.merchantChoices.map((choice) => [choice.id, choice]));
        for (const choice of merchantChoices) choices.set(choice.id, choice);
        return { ...latest, decisions: withDecisions(latest.decisions, decisions), merchantChoices: [...choices.values()] };
      });
    },
    [db],
  );

  const classify = useCallback(
    async (transactionId: string, classification: Classification, options: { remember?: boolean } = {}) => {
      const { key, current, epoch } = unlockedState();
      const transaction = current.transactions.find((item) => item.id === transactionId);
      if (!transaction) throw new Error("That transaction is not in this workspace.");
      const record = operatorEdit(transactionId, current.decisions.get(transactionId), classification);
      const merchantChoice = options.remember ? rememberChoice(transaction, classification, current.merchantChoices) : null;
      if (options.remember && !merchantChoice) throw new Error("This description names no merchant to remember.");
      await commitDecisions(key, epoch, [record], merchantChoice ? [merchantChoice] : []);
      return merchantChoice ? { merchantChoice } : {};
    },
    [commitDecisions],
  );

  const applyToSimilar = useCallback(
    async (merchantChoiceId: string) => {
      const { key, current, epoch } = unlockedState();
      const choice = current.merchantChoices.find((item) => item.id === merchantChoiceId);
      if (!choice) throw new Error("That remembered choice is not in this workspace.");
      const records = similarUncategorized(choice, current.transactions, current.decisions).map((transaction) =>
        operatorEdit(transaction.id, current.decisions.get(transaction.id), choice.classification),
      );
      if (records.length) await commitDecisions(key, epoch, records);
      return records.length;
    },
    [commitDecisions],
  );

  const undo = useCallback(
    async (transactionId: string) => {
      const { key, current, epoch } = unlockedState();
      const record = current.decisions.get(transactionId);
      if (!record) throw new Error("There is no edit to undo for this transaction.");
      await commitDecisions(key, epoch, [undoEdit(record)]);
    },
    [commitDecisions],
  );

  const retry = useCallback(() => {
    const operator = operatorRef.current;
    if (operator) void openWorkspace(operator);
    else setPhase({ kind: "signed-out" });
  }, [openWorkspace]);

  return { phase, signIn, signOut, createWithPassphrase, unlock, lock, addAccount, importStatements, loadOriginal, deleteOriginal, classify, applyToSimilar, undo, retry };
}

function withDecisions(decisions: ReadonlyMap<string, DecisionRecord>, records: readonly DecisionRecord[]): ReadonlyMap<string, DecisionRecord> {
  if (!records.length) return decisions;
  const next = new Map(decisions);
  for (const record of records) next.set(record.id, record);
  return next;
}
