// Firestore layout (all documents are owner-only per firestore.rules):
//
//   workspaces/{uid}                 WorkspaceHeader: format version, key id,
//                                    wrapped key slots. No readable content.
//   workspaces/{uid}/accounts/{id}   RecordEnvelope: AES-GCM ciphertext of an
//                                    Account, bound to its uid/collection/id.
//   workspaces/{uid}/statements/{id} RecordEnvelope of a StatementImport.
//   workspaces/{uid}/transactions/{id}
//                                    RecordEnvelope of a TransactionChunk: a
//                                    batch of one statement's transactions.
//   workspaces/{uid}/originals/{id}  RecordEnvelope of raw bytes: one chunk of
//                                    a retained original statement file.
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
  writeBatch,
  type DocumentData,
  type Firestore,
} from "firebase/firestore";
import { ACCOUNTS_COLLECTION, sortAccounts, type Account } from "./accounts";
import {
  ORIGINALS_COLLECTION,
  STATEMENTS_COLLECTION,
  TRANSACTIONS_COLLECTION,
  chunkTransactionsOf,
  joinChunks,
  sortStatements,
  sortTransactions,
  type ImportBatch,
  type StatementImport,
  type Transaction,
  type TransactionChunk,
} from "./import/statements";
import {
  CIPHER,
  FORMAT_VERSION,
  KDF,
  decryptBytes,
  decryptRecord,
  encryptBytes,
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
const recordsRef = (db: Firestore, uid: string, name: string) => collection(db, "workspaces", uid, name);
const accountsRef = (db: Firestore, uid: string) => recordsRef(db, uid, ACCOUNTS_COLLECTION);

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

async function loadRecords<T extends { id: string }>(db: Firestore, workspaceKey: WorkspaceKey, name: string): Promise<T[]> {
  const snapshot = await getDocs(recordsRef(db, workspaceKey.uid, name));
  return Promise.all(
    snapshot.docs.map(async (item) => {
      try {
        const record = await decryptRecord<T>(workspaceKey, name, item.id, envelopeFromFirestore(item.data()));
        if (record.id !== item.id) throw new Error("id mismatch");
        return record;
      } catch {
        throw new CorruptRecordError(item.id);
      }
    }),
  );
}

export async function loadAccounts(db: Firestore, workspaceKey: WorkspaceKey): Promise<Account[]> {
  return sortAccounts(await loadRecords<Account>(db, workspaceKey, ACCOUNTS_COLLECTION));
}

export interface ImportedHistory {
  statements: StatementImport[];
  transactions: Transaction[];
}

/** Decrypt every confirmed statement and its transactions. Retained originals stay encrypted until requested. */
export async function loadImportedHistory(db: Firestore, workspaceKey: WorkspaceKey): Promise<ImportedHistory> {
  const [statements, chunks] = await Promise.all([
    loadRecords<StatementImport>(db, workspaceKey, STATEMENTS_COLLECTION),
    loadRecords<TransactionChunk>(db, workspaceKey, TRANSACTIONS_COLLECTION),
  ]);
  const confirmed = new Set(statements.map((statement) => statement.id));
  // A chunk only counts once its statement record exists; both arrive in one batch.
  const transactions = chunks.filter((chunk) => confirmed.has(chunk.statementId)).flatMap(chunkTransactionsOf);
  return { statements: sortStatements(statements), transactions: sortTransactions(transactions) };
}

/**
 * Encrypt and store a confirmed import as one atomic batch: every statement,
 * its transactions, the retained original files and any new or updated
 * accounts are either all saved or none are.
 */
export async function saveImport(db: Firestore, workspaceKey: WorkspaceKey, plan: ImportBatch): Promise<void> {
  const { uid } = workspaceKey;
  const batch = writeBatch(db);
  const put = (name: string, id: string, envelope: RecordEnvelope) => batch.set(doc(recordsRef(db, uid, name), id), envelopeToFirestore(envelope));
  for (const account of plan.accounts) put(ACCOUNTS_COLLECTION, account.id, await encryptRecord(workspaceKey, ACCOUNTS_COLLECTION, account.id, account));
  for (const chunk of plan.originalChunks) put(ORIGINALS_COLLECTION, chunk.id, await encryptBytes(workspaceKey, ORIGINALS_COLLECTION, chunk.id, chunk.bytes));
  for (const chunk of plan.transactionChunks) put(TRANSACTIONS_COLLECTION, chunk.id, await encryptRecord(workspaceKey, TRANSACTIONS_COLLECTION, chunk.id, chunk));
  for (const statement of plan.statements) put(STATEMENTS_COLLECTION, statement.id, await encryptRecord(workspaceKey, STATEMENTS_COLLECTION, statement.id, statement));
  await batch.commit();
}

/** Decrypt and reassemble a retained original statement file. */
export async function loadOriginal(db: Firestore, workspaceKey: WorkspaceKey, statement: StatementImport): Promise<Uint8Array> {
  const chunks = await Promise.all(
    statement.original.chunkIds.map(async (id) => {
      const snapshot = await getDoc(doc(recordsRef(db, workspaceKey.uid, ORIGINALS_COLLECTION), id));
      if (!snapshot.exists()) throw new CorruptRecordError(id);
      try {
        return await decryptBytes(workspaceKey, ORIGINALS_COLLECTION, id, envelopeFromFirestore(snapshot.data()));
      } catch {
        throw new CorruptRecordError(id);
      }
    }),
  );
  return joinChunks(chunks);
}

/**
 * Delete a retained original file while keeping the statement record, its
 * transactions and their provenance. One atomic batch, so the statement never
 * points at a half-deleted file.
 */
export async function deleteOriginal(db: Firestore, workspaceKey: WorkspaceKey, statement: StatementImport, now = new Date()): Promise<StatementImport> {
  const updated: StatementImport = { ...statement, original: { ...statement.original, chunkIds: [], deletedAt: now.toISOString() } };
  const batch = writeBatch(db);
  for (const id of statement.original.chunkIds) batch.delete(doc(recordsRef(db, workspaceKey.uid, ORIGINALS_COLLECTION), id));
  batch.set(
    doc(recordsRef(db, workspaceKey.uid, STATEMENTS_COLLECTION), statement.id),
    envelopeToFirestore(await encryptRecord(workspaceKey, STATEMENTS_COLLECTION, statement.id, updated)),
  );
  await batch.commit();
  return updated;
}
