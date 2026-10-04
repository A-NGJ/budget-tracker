import { initializeApp, type FirebaseOptions } from "firebase/app";
import {
  GoogleAuthProvider,
  browserLocalPersistence,
  browserPopupRedirectResolver,
  connectAuthEmulator,
  initializeAuth,
  type Auth,
} from "firebase/auth";
import { connectFirestoreEmulator, initializeFirestore, memoryLocalCache, type Firestore } from "firebase/firestore";

export interface FirebaseServices {
  auth: Auth;
  db: Firestore;
  usingEmulators: boolean;
}

export type FirebaseSetup = { ok: true; services: FirebaseServices } | { ok: false; missing: string[] };

const REQUIRED = ["VITE_FIREBASE_API_KEY", "VITE_FIREBASE_AUTH_DOMAIN", "VITE_FIREBASE_PROJECT_ID", "VITE_FIREBASE_APP_ID"] as const;

let cached: FirebaseSetup | null = null;

/** Initialise Firebase once from Vite environment variables. */
export function setupFirebase(): FirebaseSetup {
  if (cached) return cached;
  const env = import.meta.env;
  const missing = REQUIRED.filter((name) => !env[name]);
  if (missing.length) return (cached = { ok: false, missing });

  const options: FirebaseOptions = {
    apiKey: env.VITE_FIREBASE_API_KEY,
    authDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: env.VITE_FIREBASE_PROJECT_ID,
    appId: env.VITE_FIREBASE_APP_ID,
  };
  const app = initializeApp(options);
  // Google sign-in is persisted so the operator is not asked to sign in on
  // every load. That token grants access to ciphertext only; the unlock
  // passphrase is still required every fresh load.
  const auth = initializeAuth(app, { persistence: browserLocalPersistence, popupRedirectResolver: browserPopupRedirectResolver });
  // Memory cache only: Firestore keeps no IndexedDB copy, so nothing about the
  // workspace, even ciphertext, outlives the tab.
  const db = initializeFirestore(app, {
    localCache: memoryLocalCache(),
    // The streaming WebChannel transport stalled after the first write in
    // WebKit (Safari's engine) during emulator tests. The workspace performs
    // only one-shot reads and writes, so long polling costs little and keeps
    // one tested transport across Chrome, Edge, Firefox and Safari.
    experimentalForceLongPolling: true,
  });

  const usingEmulators = env.VITE_FIREBASE_USE_EMULATORS === "true";
  if (usingEmulators) {
    const host = env.VITE_FIREBASE_EMULATOR_HOST || "127.0.0.1";
    connectAuthEmulator(auth, `http://${host}:${env.VITE_FIREBASE_AUTH_EMULATOR_PORT || "9099"}`, { disableWarnings: true });
    connectFirestoreEmulator(db, host, Number(env.VITE_FIREBASE_FIRESTORE_EMULATOR_PORT || "8080"));
  }
  return (cached = { ok: true, services: { auth, db, usingEmulators } });
}

export function googleProvider(): GoogleAuthProvider {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  return provider;
}
