import { describe, expect, it } from "vitest";
import {
  FORMAT_VERSION,
  MIN_PBKDF2_ITERATIONS,
  UnsupportedFormatError,
  WrongCredentialError,
  createWorkspace,
  decryptRecord,
  encryptRecord,
  rewrapKeySlot,
  unlockWorkspace,
  validatePassphrase,
} from "../../src/workspace/crypto/vault";

// Iterations are the accepted minimum to keep the suite fast; production uses
// DEFAULT_PBKDF2_ITERATIONS.
const FAST = MIN_PBKDF2_ITERATIONS;
const UID = "operator-uid";
const PASSPHRASE = "correct horse battery staple";
const account = { id: "a1", name: "Everyday", bank: "Danske Bank", currency: "DKK", createdAt: "2026-10-04T00:00:00.000Z" };

const decoder = new TextDecoder();
function containsText(bytes: Uint8Array, text: string): boolean {
  return decoder.decode(bytes).includes(text);
}

describe("workspace encryption format v1", () => {
  it("creates a versioned header whose only key material is wrapped", async () => {
    const { header, workspaceKey } = await createWorkspace(UID, PASSPHRASE, FAST);
    expect(header.formatVersion).toBe(FORMAT_VERSION);
    expect(header.cipher).toBe("AES-256-GCM");
    expect(header.keyId).toMatch(/^[0-9a-f]{32}$/);
    expect(header.keySlots.passphrase?.kdf).toBe("PBKDF2-SHA256");
    expect(header.keySlots.passphrase?.salt).toHaveLength(16);
    expect(header.keySlots.passphrase?.iv).toHaveLength(12);
    // 32-byte key + 16-byte GCM tag.
    expect(header.keySlots.passphrase?.wrappedKey).toHaveLength(48);
    expect(workspaceKey.key.extractable).toBe(false);
    expect(JSON.stringify(header)).not.toContain(PASSPHRASE);
  });

  it("rejects short passphrases", async () => {
    expect(validatePassphrase("short")).toMatch(/at least 12/);
    await expect(createWorkspace(UID, "short", FAST)).rejects.toThrow(/at least 12/);
  });

  it("unlocks with the passphrase and decrypts what it encrypted", async () => {
    const { header, workspaceKey } = await createWorkspace(UID, PASSPHRASE, FAST);
    const envelope = await encryptRecord(workspaceKey, "accounts", account.id, account);
    expect(containsText(envelope.ciphertext, "Danske")).toBe(false);
    expect(containsText(envelope.ciphertext, "Everyday")).toBe(false);

    const reopened = await unlockWorkspace(UID, header, PASSPHRASE);
    expect(reopened.key.extractable).toBe(false);
    await expect(decryptRecord(reopened, "accounts", account.id, envelope)).resolves.toEqual(account);
  });

  it("treats a NFD/NFC-different passphrase as the same credential", async () => {
    const composed = "pålidelig kodeord ø";
    const { header } = await createWorkspace(UID, composed, FAST);
    await expect(unlockWorkspace(UID, header, composed.normalize("NFD"))).resolves.toBeTruthy();
  });

  it("refuses the wrong passphrase", async () => {
    const { header } = await createWorkspace(UID, PASSPHRASE, FAST);
    await expect(unlockWorkspace(UID, header, "incorrect horse battery staple")).rejects.toBeInstanceOf(WrongCredentialError);
  });

  it("binds key slots to their owner", async () => {
    const { header } = await createWorkspace(UID, PASSPHRASE, FAST);
    await expect(unlockWorkspace("someone-else", header, PASSPHRASE)).rejects.toBeInstanceOf(WrongCredentialError);
  });

  it("binds records to owner, collection and id", async () => {
    const { workspaceKey } = await createWorkspace(UID, PASSPHRASE, FAST);
    const envelope = await encryptRecord(workspaceKey, "accounts", "a1", account);
    await expect(decryptRecord(workspaceKey, "accounts", "a2", envelope)).rejects.toThrow();
    await expect(decryptRecord(workspaceKey, "transactions", "a1", envelope)).rejects.toThrow();
    await expect(decryptRecord({ ...workspaceKey, uid: "someone-else" }, "accounts", "a1", envelope)).rejects.toThrow();
  });

  it("detects tampered ciphertext", async () => {
    const { workspaceKey } = await createWorkspace(UID, PASSPHRASE, FAST);
    const envelope = await encryptRecord(workspaceKey, "accounts", "a1", account);
    const tampered = new Uint8Array(envelope.ciphertext);
    tampered[0] ^= 1;
    await expect(decryptRecord(workspaceKey, "accounts", "a1", { ...envelope, ciphertext: tampered })).rejects.toThrow();
  });

  it("uses a fresh IV for every encryption", async () => {
    const { workspaceKey } = await createWorkspace(UID, PASSPHRASE, FAST);
    const first = await encryptRecord(workspaceKey, "accounts", "a1", account);
    const second = await encryptRecord(workspaceKey, "accounts", "a1", account);
    expect(first.iv).not.toEqual(second.iv);
    expect(first.ciphertext).not.toEqual(second.ciphertext);
  });

  it("rejects unknown versions and weakened derivation parameters", async () => {
    const { header, workspaceKey } = await createWorkspace(UID, PASSPHRASE, FAST);
    await expect(unlockWorkspace(UID, { ...header, formatVersion: 2 as never }, PASSPHRASE)).rejects.toBeInstanceOf(UnsupportedFormatError);
    const weak = { ...header, keySlots: { passphrase: { ...header.keySlots.passphrase!, iterations: 1 } } };
    await expect(unlockWorkspace(UID, weak, PASSPHRASE)).rejects.toBeInstanceOf(UnsupportedFormatError);
    const envelope = await encryptRecord(workspaceKey, "accounts", "a1", account);
    await expect(decryptRecord(workspaceKey, "accounts", "a1", { ...envelope, formatVersion: 9 as never })).rejects.toBeInstanceOf(UnsupportedFormatError);
  });

  it("adds a recovery slot and changes the passphrase without re-encrypting records", async () => {
    const { header, workspaceKey } = await createWorkspace(UID, PASSPHRASE, FAST);
    const envelope = await encryptRecord(workspaceKey, "accounts", account.id, account);

    const withRecovery = await rewrapKeySlot(UID, header, { slot: "passphrase", secret: PASSPHRASE }, "recovery", "RECOVERY-KEY-0001-0002", FAST);
    const changed = await rewrapKeySlot(UID, withRecovery, { slot: "recovery", secret: "RECOVERY-KEY-0001-0002" }, "passphrase", "a brand new passphrase", FAST);

    expect(changed.keyId).toBe(header.keyId);
    await expect(unlockWorkspace(UID, changed, PASSPHRASE)).rejects.toBeInstanceOf(WrongCredentialError);
    const viaNew = await unlockWorkspace(UID, changed, "a brand new passphrase");
    const viaRecovery = await unlockWorkspace(UID, changed, "RECOVERY-KEY-0001-0002", "recovery");
    await expect(decryptRecord(viaNew, "accounts", account.id, envelope)).resolves.toEqual(account);
    await expect(decryptRecord(viaRecovery, "accounts", account.id, envelope)).resolves.toEqual(account);
  });
});
