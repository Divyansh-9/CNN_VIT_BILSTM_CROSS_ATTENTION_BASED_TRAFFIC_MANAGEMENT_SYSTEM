// The sign-in client (owner's request, 2026-11-14). The only module besides
// workbench.js that may POST, and only to the server's /auth routes: register,
// login, logout, forgot and reset. It never reaches a data or signal route, and
// a test pins both.
//
// The session lives in an HttpOnly cookie the browser holds; this code never
// sees it, stores it or sends it anywhere itself. Nothing about the session is
// kept in localStorage. Who is signed in is always asked of the server.

export const AUTH_ACTIONS = ["register", "login", "logout", "forgot", "reset"];

/** Fired when any read answers 401: the session ended or expired on the server. */
export const SIGNED_OUT_EVENT = "stms:signed-out";

export function announceSignedOut() {
  globalThis.window?.dispatchEvent(new CustomEvent(SIGNED_OUT_EVENT));
}

async function body(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

// Resolves to { ok, status, data }. A network failure is status 0, never a throw.
export async function authPost(action, payload = {}, fetcher = globalThis.fetch) {
  if (!AUTH_ACTIONS.includes(action)) throw new Error(`auth: ${action} is not an auth action`);
  let response;
  try {
    response = await fetcher(`/auth/${action}`, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    return { ok: false, status: 0, data: { detail: "The server is not answering. Check that it is running." } };
  }
  return { ok: response.ok, status: response.status, data: await body(response) };
}

// The signed-in user, null when signed out, or undefined when the server could not be reached.
export async function currentUser(fetcher = globalThis.fetch) {
  let response;
  try {
    response = await fetcher("/auth/me", {
      method: "GET", credentials: "same-origin", cache: "no-store", headers: { accept: "application/json" },
    });
  } catch {
    return undefined;
  }
  if (response.status === 401) return null;
  if (!response.ok) return undefined;
  return (await body(response)).user ?? null;
}

// The password rules the server enforces (server/auth.py password_problems), shown
// as a checklist while typing. The server stays the authority: it checks again.
export function passwordChecks(password, username = "", email = "") {
  const lowered = password.toLowerCase();
  const personal = [username.toLowerCase(), email.toLowerCase().split("@")[0]].filter((p) => p.length >= 3);
  const weak = ["password", "passw0rd", "qwerty", "123456", "letmein", "welcome", "admin", "iloveyou", "abc123",
    "traffic", "stms"];
  return [
    { id: "length", label: "10 to 128 characters", ok: password.length >= 10 && password.length <= 128 },
    { id: "lower", label: "A lowercase letter", ok: /[a-z]/.test(password) },
    { id: "upper", label: "An uppercase letter", ok: /[A-Z]/.test(password) },
    { id: "digit", label: "A number", ok: /[0-9]/.test(password) },
    { id: "symbol", label: "A symbol, such as ! or #", ok: /[^A-Za-z0-9]/.test(password) },
    { id: "personal", label: "Not your username or e-mail name",
      ok: password.length > 0 && !personal.some((p) => lowered.includes(p)) },
    { id: "common", label: "No common words like 'password'",
      ok: password.length > 0 && !weak.some((w) => lowered.includes(w)) },
  ];
}

export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const USERNAME_PATTERN = /^[A-Za-z][A-Za-z0-9_.-]{2,31}$/;
