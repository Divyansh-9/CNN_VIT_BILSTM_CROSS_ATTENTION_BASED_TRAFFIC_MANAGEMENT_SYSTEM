import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AuthScreen } from "./Auth.jsx";
import { SIGNED_OUT_EVENT, authPost, currentUser } from "./auth.js";
import { Icon } from "./icons.jsx";
import styles from "./Auth.module.css";

// Nothing of the project renders until the server says someone is signed in
// (owner's request, 2026-11-14). The gate asks GET /auth/me; the HttpOnly session
// cookie is the browser's and the server's business, never this code's.
//
//   checking      a loading screen, and nothing else
//   signed-out    the sign-in screens (#login, #register, #forgot, #reset/<token>)
//   unreachable   the sign-in screen, saying the server is not answering
//   signed-in     the project: home, explorer and console, exactly as before
//
// The gate re-asks every minute, when the tab comes back into view and when the
// browser restores the page from its back/forward cache. Any data read that
// answers 401 also signs the page out (api.js, workbench.js). So an expired
// session, a sign-out in another tab or the back button after signing out all
// end at the sign-in screen, and the console's data unmounts with it.

const AuthContext = createContext(null);

/** { user, signOut } while signed in; null outside the gate (and in tests that render pages alone). */
export function useAuth() {
  return useContext(AuthContext);
}

const RECHECK_MS = 60_000;
const EXPIRED = "Your session has ended. Sign in again to continue.";

export function authRoute(hash) {
  const raw = String(hash || "").replace(/^#\/?/, "");
  const reset = /^reset\/([A-Za-z0-9_-]{20,128})$/.exec(raw);
  if (reset) return { view: "reset", token: reset[1] };
  if (raw === "register") return { view: "register" };
  if (raw === "forgot") return { view: "forgot" };
  return { view: "login" };
}

export function AuthGate({ children, fetcher }) {
  const [state, setState] = useState({ phase: "checking", user: null, notice: null });
  const [route, setRoute] = useState(() => authRoute(window.location.hash));
  const phase = useRef("checking");
  phase.current = state.phase;

  const check = useCallback(async () => {
    const user = await currentUser(fetcher);
    if (user === undefined) {
      // A dropped network does not sign anyone out; it only blocks signing in.
      setState((s) => (s.phase === "signed-in" ? s : { phase: "unreachable", user: null, notice: null }));
    } else if (user === null) {
      setState((s) => ({ phase: "signed-out", user: null, notice: s.phase === "signed-in" ? EXPIRED : s.notice }));
    } else {
      setState((s) => ({ phase: "signed-in", user, notice: s.notice && s.phase === "signed-in" ? s.notice : null }));
    }
  }, [fetcher]);

  useEffect(() => { check(); }, [check]);

  useEffect(() => {
    const signedOut = () => {
      if (phase.current === "signed-in") setState({ phase: "signed-out", user: null, notice: EXPIRED });
    };
    const follow = () => setRoute(authRoute(window.location.hash));
    window.addEventListener(SIGNED_OUT_EVENT, signedOut);
    window.addEventListener("hashchange", follow);
    return () => {
      window.removeEventListener(SIGNED_OUT_EVENT, signedOut);
      window.removeEventListener("hashchange", follow);
    };
  }, []);

  useEffect(() => {
    if (state.phase !== "signed-in") return undefined;
    const timer = setInterval(check, RECHECK_MS);
    const shown = (event) => { if (event.persisted) check(); };
    const visible = () => { if (document.visibilityState === "visible") check(); };
    window.addEventListener("pageshow", shown);
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(timer);
      window.removeEventListener("pageshow", shown);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [state.phase, check]);

  const signedIn = useCallback((user) => {
    setState({ phase: "signed-in", user, notice: null });
    // EXPECTED FLOW: after signing in, the STMS home page.
    window.location.hash = "#home";
  }, []);

  const signOut = useCallback(async () => {
    await authPost("logout", {}, fetcher);
    // Replace, not push: the page before this is the console, and Back must not offer it.
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#login`);
    setRoute({ view: "login" });
    setState({ phase: "signed-out", user: null, notice: "You have signed out." });
  }, [fetcher]);

  if (state.phase === "checking") {
    return (
      <div className={styles.loading} role="status" aria-live="polite">
        <span className={styles.spinner} aria-hidden="true" />
        <span>Checking your session…</span>
      </div>
    );
  }
  if (state.phase !== "signed-in") {
    return (
      <AuthScreen route={route} fetcher={fetcher} onSignedIn={signedIn} retry={check}
                  unreachable={state.phase === "unreachable"} notice={state.notice} />
    );
  }
  return <AuthContext.Provider value={{ user: state.user, signOut }}>{children}</AuthContext.Provider>;
}

/** The signed-in person and Sign out, for the page bars. Renders nothing outside the gate. */
export function AccountMenu({ compact = false }) {
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const away = (event) => { if (box.current && !box.current.contains(event.target)) setOpen(false); };
    const escape = (event) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  if (!auth) return null;
  const { user, signOut } = auth;
  const initials = user.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
  const leave = async () => {
    setLeaving(true);
    await signOut();
  };
  return (
    <div className={styles.account} ref={box} data-account-menu="true">
      <button type="button" className={styles.accountButton} aria-haspopup="true" aria-expanded={open}
              onClick={() => setOpen((v) => !v)} title={`Signed in as ${user.username}`}>
        <span className={styles.avatar} aria-hidden="true">{initials || <Icon name="user" size={14} />}</span>
        {!compact && <span className={styles.accountName}>{user.username}</span>}
        <Icon name="caret-down" size={12} />
      </button>
      {open && (
        <div className={styles.accountMenu} role="menu">
          <p className={styles.accountWho}>
            <strong>{user.full_name}</strong>
            <span>{user.email}</span>
          </p>
          <button type="button" role="menuitem" className={styles.signOut} onClick={leave} disabled={leaving}>
            <Icon name="arrow-left" size={15} />{leaving ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}
