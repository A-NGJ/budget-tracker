// Firestore rules tests. Run through `npm run test:rules`, which starts the
// Firestore emulator; they never touch a real project.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterAll, beforeAll, beforeEach, describe, it } from "vitest";
import { assertFails, assertSucceeds, initializeTestEnvironment, type RulesTestEnvironment } from "@firebase/rules-unit-testing";
import { Bytes, deleteDoc, doc, getDoc, getDocs, collection, serverTimestamp, setDoc, updateDoc, type Firestore } from "firebase/firestore";

const OWNER = "owner-uid";
const OTHER = "other-uid";
const KEY_ID = "0123456789abcdef0123456789abcdef";
const google = { firebase: { sign_in_provider: "google.com" as const } };

let env: RulesTestEnvironment;

const bytes = (length: number) => Bytes.fromUint8Array(new Uint8Array(length).fill(7));
const slot = () => ({ kdf: "PBKDF2-SHA256", iterations: 600000, salt: bytes(16), iv: bytes(12), wrappedKey: bytes(48) });
const header = (overrides: Record<string, unknown> = {}) => ({ formatVersion: 1, cipher: "AES-256-GCM", keyId: KEY_ID, keySlots: { passphrase: slot() }, createdAt: serverTimestamp(), ...overrides });
const envelope = (overrides: Record<string, unknown> = {}) => ({ formatVersion: 1, keyId: KEY_ID, iv: bytes(12), ciphertext: bytes(64), updatedAt: serverTimestamp(), ...overrides });

const asOwner = () => env.authenticatedContext(OWNER, google).firestore() as unknown as Firestore;
const asOther = () => env.authenticatedContext(OTHER, google).firestore() as unknown as Firestore;
const anonymous = () => env.unauthenticatedContext().firestore() as unknown as Firestore;

async function seedWorkspace() {
  await env.withSecurityRulesDisabled(async (context) => {
    const db = context.firestore() as unknown as Firestore;
    await setDoc(doc(db, "workspaces", OWNER), header());
    await setDoc(doc(db, "workspaces", OWNER, "accounts", "acc-1"), envelope());
  });
}

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-budget-tracker-rules",
    firestore: { rules: readFileSync(resolve(__dirname, "../../../firestore.rules"), "utf8") },
  });
});

afterAll(async () => {
  await env?.cleanup();
});

beforeEach(async () => {
  await env.clearFirestore();
});

describe("workspace header", () => {
  it("lets the owner create and read their workspace", async () => {
    await assertSucceeds(setDoc(doc(asOwner(), "workspaces", OWNER), header()));
    await assertSucceeds(getDoc(doc(asOwner(), "workspaces", OWNER)));
  });

  it("rejects unauthenticated reads and writes", async () => {
    await seedWorkspace();
    await assertFails(getDoc(doc(anonymous(), "workspaces", OWNER)));
    await assertFails(setDoc(doc(anonymous(), "workspaces", "anyone"), header()));
  });

  it("rejects another user's reads and writes", async () => {
    await seedWorkspace();
    await assertFails(getDoc(doc(asOther(), "workspaces", OWNER)));
    await assertFails(setDoc(doc(asOther(), "workspaces", OWNER), header()));
    await assertFails(getDocs(collection(asOther(), "workspaces")));
  });

  it("rejects sign-in providers other than Google", async () => {
    const password = env.authenticatedContext(OWNER, { firebase: { sign_in_provider: "password" as const } }).firestore() as unknown as Firestore;
    await assertFails(setDoc(doc(password, "workspaces", OWNER), header()));
  });

  it("does not allow overwriting, updating or deleting an existing header", async () => {
    await seedWorkspace();
    await assertFails(setDoc(doc(asOwner(), "workspaces", OWNER), header({ keyId: "f".repeat(32) })));
    await assertFails(updateDoc(doc(asOwner(), "workspaces", OWNER), { keyId: "f".repeat(32) }));
    await assertFails(deleteDoc(doc(asOwner(), "workspaces", OWNER)));
  });

  it("rejects malformed headers and readable fields", async () => {
    const db = asOwner();
    const ref = doc(db, "workspaces", OWNER);
    await assertFails(setDoc(ref, header({ formatVersion: 2 })));
    await assertFails(setDoc(ref, header({ cipher: "none" })));
    await assertFails(setDoc(ref, header({ keySlots: {} })));
    await assertFails(setDoc(ref, header({ keySlots: { passphrase: { ...slot(), iterations: 1000 } } })));
    await assertFails(setDoc(ref, header({ keySlots: { passphrase: { ...slot(), wrappedKey: "plain" } } })));
    await assertFails(setDoc(ref, header({ passphrase: "hunter2hunter2" })));
  });
});

describe("encrypted account records", () => {
  it("lets the owner write and list encrypted accounts", async () => {
    await seedWorkspace();
    await assertSucceeds(setDoc(doc(asOwner(), "workspaces", OWNER, "accounts", "acc-2"), envelope()));
    await assertSucceeds(getDocs(collection(asOwner(), "workspaces", OWNER, "accounts")));
  });

  it("rejects unauthenticated and other-user access", async () => {
    await seedWorkspace();
    await assertFails(getDocs(collection(anonymous(), "workspaces", OWNER, "accounts")));
    await assertFails(getDoc(doc(anonymous(), "workspaces", OWNER, "accounts", "acc-1")));
    await assertFails(setDoc(doc(anonymous(), "workspaces", OWNER, "accounts", "x"), envelope()));
    await assertFails(getDocs(collection(asOther(), "workspaces", OWNER, "accounts")));
    await assertFails(getDoc(doc(asOther(), "workspaces", OWNER, "accounts", "acc-1")));
    await assertFails(setDoc(doc(asOther(), "workspaces", OWNER, "accounts", "acc-1"), envelope()));
  });

  it("requires an existing workspace and its key id", async () => {
    await assertFails(setDoc(doc(asOwner(), "workspaces", OWNER, "accounts", "acc-1"), envelope()));
    await seedWorkspace();
    await assertFails(setDoc(doc(asOwner(), "workspaces", OWNER, "accounts", "acc-2"), envelope({ keyId: "f".repeat(32) })));
  });

  it("rejects readable fields and non-binary ciphertext", async () => {
    await seedWorkspace();
    const ref = doc(asOwner(), "workspaces", OWNER, "accounts", "acc-2");
    await assertFails(setDoc(ref, { ...envelope(), name: "Everyday" }));
    await assertFails(setDoc(ref, envelope({ ciphertext: "Everyday · Danske Bank · DKK" })));
    await assertFails(setDoc(ref, envelope({ formatVersion: 2 })));
  });

  it("does not allow deleting records yet", async () => {
    await seedWorkspace();
    await assertFails(deleteDoc(doc(asOwner(), "workspaces", OWNER, "accounts", "acc-1")));
  });
});

describe("everything else", () => {
  it("is denied", async () => {
    await assertFails(setDoc(doc(asOwner(), "transactions", "t1"), { amount: 1 }));
    await assertFails(getDoc(doc(asOwner(), "users", OWNER)));
  });
});
