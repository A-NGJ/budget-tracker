// Firestore layout (all documents are owner-only per firestore.rules):
//
//   workspaces/{uid}                 WorkspaceHeader: format version, key id,
//                                    wrapped key slots. No readable content.
//   workspaces/{uid}/accounts/{id}   RecordEnvelope: AES-GCM ciphertext of an
//                                    Account, bound to its uid/collection/id.
//
// Only ciphertext, random salts/IVs, KDF parameters and opaque ids leave the
// browser. Readable records and keys never reach this module's writes.
import {
  Bytes,
  collection,
  doc,
  getDoc,
  getDocs,
  runTransaction,
  serverTimestamp,
  setDoc,
  type DocumentData,
  type Firestore,
} from "firebase/firestore";
import { ACCOUNTS_COLLECTION, sortAccounts, type Account } from "./accounts";
import {
  CIPHER,
  FORMAT_VERSION,
  KDF,
  decryptRecord,
  encryptRecord,
  type KeySlot,
  type RecordEnvelope,
  type SlotName,
  type WorkspaceHeader,
  type WorkspaceKey,
} from "./crypto/vault";

export class WorkspaceExistsError extends Error {
  constructor() {
    super("A workspace already exists for this Google account.");
    this.name = "WorkspaceExistsError";
  }
}

export class CorruptRecordError extends Error {
  constructor(recordId: string) {
    super(`Encrypted record ${recordId} could not be decrypted.`);
    this.name = "CorruptRecordError";
  }
}

const workspaceRef = (db: Firestore, uid: string) => doc(db, "workspaces", uid);
const accountsRef = (db: Firestore, uid: string) => collection(db, "workspaces", uid, ACCOUNTS_COLLECTION);

function slotToFirestore(slot: KeySlot): DocumentData {
  return {
    kdf: slot.kdf,
    iterations: slot.iterations,
    salt: Bytes.fromUint8Array(slot.salt),
    iv: Bytes.fromUint8Array(slot.iv),
    wrappedKey: Bytes.fromUint8Array(slot.wrappedKey),
  };
}

function slotFromFirestore(data: DocumentData): KeySlot {
  if (data.kdf !== KDF || !(data.salt instanceof Bytes) || !(data.iv instanceof Bytes) || !(data.wrappedKey instanceof Bytes)) {
    throw new Error("Workspace key slot is malformed.");
  }
  return {
    kdf: KDF,
    iterations: Number(data.iterations),
    salt: data.salt.toUint8Array(),
    iv: data.iv.toUint8Array(),
    wrappedKey: data.wrappedKey.toUint8Array(),
  };
}

function headerToFirestore(header: WorkspaceHeader): DocumentData {
  const keySlots: DocumentData = {};
  for (const [name, slot] of Object.entries(header.keySlots)) if (slot) keySlots[name] = slotToFirestore(slot);
  return { formatVersion: header.formatVersion, cipher: header.cipher, keyId: header.keyId, keySlots };
}

function headerFromFirestore(data: DocumentData): WorkspaceHeader {
  const keySlots: Partial<Record<SlotName, KeySlot>> = {};
  for (const name of ["passphrase", "recovery"] as const) {
    if (data.keySlots?.[name]) keySlots[name] = slotFromFirestore(data.keySlots[name]);
  }
  return { formatVersion: data.formatVersion, cipher: data.cipher, keyId: String(data.keyId), keySlots };
}

function envelopeToFirestore(envelope: RecordEnvelope): DocumentData {
  return {
    formatVersion: envelope.formatVersion,
    keyId: envelope.keyId,
    iv: Bytes.fromUint8Array(envelope.iv),
    ciphertext: Bytes.fromUint8Array(envelope.ciphertext),
    updatedAt: serverTimestamp(),
  };
}

function envelopeFromFirestore(data: DocumentData): RecordEnvelope {
  if (!(data.iv instanceof Bytes) || !(data.ciphertext instanceof Bytes)) throw new Error("Encrypted record is malformed.");
  return { formatVersion: data.formatVersion, keyId: String(data.keyId), iv: data.iv.toUint8Array(), ciphertext: data.ciphertext.toUint8Array() };
}

/** Read the workspace header, or null when this Google account has no workspace yet. */
export async function loadWorkspaceHeader(db: Firestore, uid: string): Promise<WorkspaceHeader | null> {
  const snapshot = await getDoc(workspaceRef(db, uid));
  return snapshot.exists() ? headerFromFirestore(snapshot.data()) : null;
}

/** Store a new workspace header. Refuses to overwrite an existing workspace. */
export async function saveNewWorkspaceHeader(db: Firestore, uid: string, header: WorkspaceHeader): Promise<void> {
  if (header.formatVersion !== FORMAT_VERSION || header.cipher !== CIPHER) throw new Error("Refusing to store an unsupported header.");
  await runTransaction(db, async (transaction) => {
    const ref = workspaceRef(db, uid);
    if ((await transaction.get(ref)).exists()) throw new WorkspaceExistsError();
    transaction.set(ref, { ...headerToFirestore(header), createdAt: serverTimestamp() });
  });
}

export async function saveAccount(db: Firestore, workspaceKey: WorkspaceKey, account: Account): Promise<void> {
  const envelope = await encryptRecord(workspaceKey, ACCOUNTS_COLLECTION, account.id, account);
  await setDoc(doc(accountsRef(db, workspaceKey.uid), account.id), envelopeToFirestore(envelope));
}

export async function loadAccounts(db: Firestore, workspaceKey: WorkspaceKey): Promise<Account[]> {
  const snapshot = await getDocs(accountsRef(db, workspaceKey.uid));
  const accounts = await Promise.all(
    snapshot.docs.map(async (item) => {
      try {
        const account = await decryptRecord<Account>(workspaceKey, ACCOUNTS_COLLECTION, item.id, envelopeFromFirestore(item.data()));
        if (account.id !== item.id) throw new Error("id mismatch");
        return account;
      } catch {
        throw new CorruptRecordError(item.id);
      }
    }),
  );
  return sortAccounts(accounts);
}
