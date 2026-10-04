// Browser-only workspace encryption, format version 1.
//
// One random AES-256-GCM workspace key encrypts every record. The workspace key
// never leaves the browser in readable form: it is stored only inside key
// slots, each wrapping it under a key derived from one decryption credential.
// Version 1 ships the passphrase slot; the recovery-key slot and credential
// changes (issue #15) add or rewrap slots without touching record ciphertext.
// See docs/adr/0003-workspace-encryption-format.md.

export const FORMAT_VERSION = 1;
export const CIPHER = "AES-256-GCM";
export const KDF = "PBKDF2-SHA256";
/** OWASP 2023 guidance for PBKDF2-HMAC-SHA256. */
export const DEFAULT_PBKDF2_ITERATIONS = 600_000;
/** Lower bound accepted when reading a slot, so a tampered header cannot weaken derivation. */
export const MIN_PBKDF2_ITERATIONS = 100_000;
export const MIN_PASSPHRASE_LENGTH = 12;

const SALT_BYTES = 16;
const IV_BYTES = 12;
const KEY_ID_BYTES = 16;

export type SlotName = "passphrase" | "recovery";

/** A wrapped copy of the workspace key. Safe to store in the cloud. */
export interface KeySlot {
  kdf: typeof KDF;
  iterations: number;
  salt: Uint8Array;
  iv: Uint8Array;
  wrappedKey: Uint8Array;
}

/** Non-secret workspace metadata stored at `workspaces/{uid}`. */
export interface WorkspaceHeader {
  formatVersion: typeof FORMAT_VERSION;
  cipher: typeof CIPHER;
  keyId: string;
  keySlots: Partial<Record<SlotName, KeySlot>>;
}

/** An encrypted record as stored in the cloud. Carries no readable content. */
export interface RecordEnvelope {
  formatVersion: typeof FORMAT_VERSION;
  keyId: string;
  iv: Uint8Array;
  ciphertext: Uint8Array;
}

/** The unlocked workspace key. Lives in memory only and is not extractable. */
export interface WorkspaceKey {
  uid: string;
  keyId: string;
  key: CryptoKey;
}

export class WrongCredentialError extends Error {
  constructor() {
    super("That passphrase does not unlock this workspace.");
    this.name = "WrongCredentialError";
  }
}

export class UnsupportedFormatError extends Error {
  constructor(detail: string) {
    super(`Unsupported encrypted workspace format: ${detail}`);
    this.name = "UnsupportedFormatError";
  }
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function randomBytes(length: number): Uint8Array<ArrayBuffer> {
  return crypto.getRandomValues(new Uint8Array(length));
}

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

// Copy into a fresh ArrayBuffer-backed view; WebCrypto rejects views over
// SharedArrayBuffer and some engines reject foreign-realm buffers.
function buffer(bytes: Uint8Array): Uint8Array<ArrayBuffer> {
  return new Uint8Array(bytes);
}

/** Additional authenticated data binding a key slot to its owner and purpose. */
export function slotAad(uid: string, slot: SlotName, keyId: string): Uint8Array<ArrayBuffer> {
  return encoder.encode(`budget-tracker/v${FORMAT_VERSION}/key-slot/${uid}/${slot}/${keyId}`);
}

/**
 * Additional authenticated data binding a record to its owner, collection and
 * document id, so ciphertext copied to another place fails to decrypt.
 */
export function recordAad(uid: string, collection: string, recordId: string, keyId: string): Uint8Array<ArrayBuffer> {
  return encoder.encode(`budget-tracker/v${FORMAT_VERSION}/record/${uid}/${collection}/${recordId}/${keyId}`);
}

async function deriveWrappingKey(secret: string, salt: Uint8Array, iterations: number): Promise<CryptoKey> {
  const material = await crypto.subtle.importKey("raw", encoder.encode(secret.normalize("NFC")), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt: buffer(salt), iterations },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["wrapKey", "unwrapKey"],
  );
}

async function wrapIntoSlot(uid: string, slot: SlotName, keyId: string, workspaceKey: CryptoKey, secret: string, iterations: number): Promise<KeySlot> {
  const salt = randomBytes(SALT_BYTES);
  const iv = randomBytes(IV_BYTES);
  const wrappingKey = await deriveWrappingKey(secret, salt, iterations);
  const wrapped = await crypto.subtle.wrapKey("raw", workspaceKey, wrappingKey, { name: "AES-GCM", iv, additionalData: slotAad(uid, slot, keyId) });
  return { kdf: KDF, iterations, salt, iv, wrappedKey: new Uint8Array(wrapped) };
}

async function unwrapFromSlot(uid: string, header: WorkspaceHeader, slot: SlotName, secret: string, extractable: boolean): Promise<CryptoKey> {
  assertSupportedHeader(header);
  const keySlot = header.keySlots[slot];
  if (!keySlot) throw new UnsupportedFormatError(`missing ${slot} key slot`);
  if (keySlot.kdf !== KDF) throw new UnsupportedFormatError(`key derivation ${String(keySlot.kdf)}`);
  if (!Number.isInteger(keySlot.iterations) || keySlot.iterations < MIN_PBKDF2_ITERATIONS) {
    throw new UnsupportedFormatError("key derivation iterations below the accepted minimum");
  }
  const wrappingKey = await deriveWrappingKey(secret, keySlot.salt, keySlot.iterations);
  try {
    return await crypto.subtle.unwrapKey(
      "raw",
      buffer(keySlot.wrappedKey),
      wrappingKey,
      { name: "AES-GCM", iv: buffer(keySlot.iv), additionalData: slotAad(uid, slot, header.keyId) },
      { name: "AES-GCM", length: 256 },
      extractable,
      ["encrypt", "decrypt"],
    );
  } catch {
    // GCM authentication failure: wrong credential or a tampered slot.
    throw new WrongCredentialError();
  }
}

export function assertSupportedHeader(header: WorkspaceHeader): void {
  if (header.formatVersion !== FORMAT_VERSION) throw new UnsupportedFormatError(`version ${String(header.formatVersion)}`);
  if (header.cipher !== CIPHER) throw new UnsupportedFormatError(`cipher ${String(header.cipher)}`);
}

export function validatePassphrase(passphrase: string): string | null {
  if (passphrase.normalize("NFC").length < MIN_PASSPHRASE_LENGTH) {
    return `Use at least ${MIN_PASSPHRASE_LENGTH} characters.`;
  }
  return null;
}

/**
 * Create a new workspace key protected by the passphrase. Returns the header to
 * store and the unlocked in-memory key.
 */
export async function createWorkspace(uid: string, passphrase: string, iterations = DEFAULT_PBKDF2_ITERATIONS): Promise<{ header: WorkspaceHeader; workspaceKey: WorkspaceKey }> {
  const problem = validatePassphrase(passphrase);
  if (problem) throw new Error(problem);
  const keyId = toHex(randomBytes(KEY_ID_BYTES));
  // Extractable only for the moment it takes to wrap it; the session copy is not.
  const raw = randomBytes(32);
  const exportable = await crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, true, ["encrypt", "decrypt"]);
  const passphraseSlot = await wrapIntoSlot(uid, "passphrase", keyId, exportable, passphrase, iterations);
  const key = await crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
  raw.fill(0);
  return {
    header: { formatVersion: FORMAT_VERSION, cipher: CIPHER, keyId, keySlots: { passphrase: passphraseSlot } },
    workspaceKey: { uid, keyId, key },
  };
}

/** Unlock the workspace key with a credential. Throws WrongCredentialError. */
export async function unlockWorkspace(uid: string, header: WorkspaceHeader, secret: string, slot: SlotName = "passphrase"): Promise<WorkspaceKey> {
  const key = await unwrapFromSlot(uid, header, slot, secret, false);
  return { uid, keyId: header.keyId, key };
}

/**
 * Return a header with `targetSlot` (re)wrapped under `newSecret`, authorised
 * by an existing credential. Records are untouched: this is the primitive for
 * passphrase changes and recovery-key generation.
 */
export async function rewrapKeySlot(
  uid: string,
  header: WorkspaceHeader,
  authorising: { slot: SlotName; secret: string },
  targetSlot: SlotName,
  newSecret: string,
  iterations = DEFAULT_PBKDF2_ITERATIONS,
): Promise<WorkspaceHeader> {
  const exportable = await unwrapFromSlot(uid, header, authorising.slot, authorising.secret, true);
  const slot = await wrapIntoSlot(uid, targetSlot, header.keyId, exportable, newSecret, iterations);
  return { ...header, keySlots: { ...header.keySlots, [targetSlot]: slot } };
}

export async function encryptRecord(workspaceKey: WorkspaceKey, collection: string, recordId: string, value: unknown): Promise<RecordEnvelope> {
  const iv = randomBytes(IV_BYTES);
  const plaintext = encoder.encode(JSON.stringify(value));
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: recordAad(workspaceKey.uid, collection, recordId, workspaceKey.keyId) },
    workspaceKey.key,
    plaintext,
  );
  return { formatVersion: FORMAT_VERSION, keyId: workspaceKey.keyId, iv, ciphertext: new Uint8Array(ciphertext) };
}

export async function decryptRecord<T>(workspaceKey: WorkspaceKey, collection: string, recordId: string, envelope: RecordEnvelope): Promise<T> {
  if (envelope.formatVersion !== FORMAT_VERSION) throw new UnsupportedFormatError(`record version ${String(envelope.formatVersion)}`);
  if (envelope.keyId !== workspaceKey.keyId) throw new UnsupportedFormatError("record encrypted under a different workspace key");
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: buffer(envelope.iv), additionalData: recordAad(workspaceKey.uid, collection, recordId, workspaceKey.keyId) },
    workspaceKey.key,
    buffer(envelope.ciphertext),
  );
  return JSON.parse(decoder.decode(plaintext)) as T;
}
