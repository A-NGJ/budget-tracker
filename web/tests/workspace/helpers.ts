import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const PROJECT_ID = "demo-budget-tracker";
export const FIRESTORE = "http://127.0.0.1:8080";
export const AUTH = "http://127.0.0.1:9099";
const DOCUMENTS = `${FIRESTORE}/v1/projects/${PROJECT_ID}/databases/(default)/documents`;

export async function resetEmulators(request: APIRequestContext) {
  expect((await request.delete(`${FIRESTORE}/emulator/v1/projects/${PROJECT_ID}/databases/(default)/documents`)).ok()).toBe(true);
  expect((await request.delete(`${AUTH}/emulator/v1/projects/${PROJECT_ID}/accounts`)).ok()).toBe(true);
}

/** Sign in through the Auth emulator's Google popup as a new account. */
export async function signInWithGoogle(page: Page, email: string) {
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Sign in with Google" }).click();
  const popup = await popupPromise;
  await popup.waitForLoadState("domcontentloaded");
  await popup.locator(".js-new-account").click();
  await popup.locator("#email-input").fill(email);
  await popup.locator("#display-name-input").fill("Test Operator");
  await popup.locator("#sign-in").click();
  await popup.waitForEvent("close");
}

/** Admin read of a document or collection, bypassing rules (emulator only). */
export async function adminGet(request: APIRequestContext, path: string) {
  const response = await request.get(`${DOCUMENTS}/${path}`, { headers: { Authorization: "Bearer owner" } });
  expect(response.ok()).toBe(true);
  return response.json();
}

/** Sign a user in through the Auth emulator REST API and return a real emulator ID token. */
export async function emulatorGoogleToken(request: APIRequestContext, sub: string, email: string) {
  const response = await request.post(`${AUTH}/identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=demo-api-key`, {
    data: {
      requestUri: "http://127.0.0.1",
      postBody: `id_token=${encodeURIComponent(JSON.stringify({ sub, email, email_verified: true }))}&providerId=google.com`,
      returnSecureToken: true,
      returnIdpCredential: true,
    },
  });
  expect(response.ok()).toBe(true);
  const body = await response.json();
  return { idToken: body.idToken as string, uid: body.localId as string };
}

export function documentsUrl(path: string) {
  return `${DOCUMENTS}/${path}`;
}

/** All text the browser keeps in persistent storage for this origin. */
export async function persistentStorageDump(page: Page) {
  return page.evaluate(async () => {
    const local = Object.entries(localStorage).map(([key, value]) => `${key}=${value}`);
    const session = Object.entries(sessionStorage).map(([key, value]) => `${key}=${value}`);
    const databases = "databases" in indexedDB ? (await indexedDB.databases()).map((db) => db.name ?? "") : [];
    const cacheKeys = "caches" in window ? await caches.keys() : [];
    return { local, session, databases, cacheKeys };
  });
}
