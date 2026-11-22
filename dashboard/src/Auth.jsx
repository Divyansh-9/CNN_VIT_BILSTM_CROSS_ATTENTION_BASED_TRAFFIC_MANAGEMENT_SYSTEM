import { forwardRef, useEffect, useId, useRef, useState } from "react";
import { EMAIL_PATTERN, USERNAME_PATTERN, authPost, passwordChecks } from "./auth.js";
import { Icon } from "./icons.jsx";
import { SITE } from "./site.js";
import styles from "./Auth.module.css";

// The screens before sign-in: Sign in, Create account, Forgot password and
// Choose a new password (owner's request, 2026-11-14). Every check here is a
// convenience: the server (server/auth.py) checks everything again and is the
// authority. No password is kept after a request, and nothing is stored in the
// browser except the HttpOnly cookie the server sets.

// Move between the sign-in screens. `replace` drops the current entry from history
// (a used reset link must not be one Back away), and the screen is told either way,
// because replaceState and a hash that does not change fire no hashchange.
function go(hash, { replace = false } = {}) {
  if (replace || window.location.hash === hash) {
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = hash;
  }
}

function CityBackdrop() {
  // A drawn street grid with moving light, not a picture of real traffic.
  const roads = [120, 300, 480, 660];
  return (
    <svg className={styles.city} viewBox="0 0 800 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <pattern id="authGrid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M40 0H0V40" fill="none" className={styles.gridLine} />
        </pattern>
      </defs>
      <rect width="800" height="800" fill="url(#authGrid)" />
      {roads.map((p) => (
        <g key={p}>
          <line x1="0" y1={p} x2="800" y2={p} className={styles.road} />
          <line x1={p} y1="0" x2={p} y2="800" className={styles.road} />
          <line x1="0" y1={p} x2="800" y2={p} className={styles.flow} style={{ animationDelay: `${-p / 90}s` }} />
          <line x1={p} y1="0" x2={p} y2="800" className={`${styles.flow} ${styles.flowReverse}`}
                style={{ animationDelay: `${-p / 70}s` }} />
        </g>
      ))}
      {roads.flatMap((x) => roads.map((y) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="5" className={styles.node} style={{ animationDelay: `${(x + y) / 400}s` }} />
      )))}
    </svg>
  );
}

function BrandPanel() {
  const features = [
    ["video-camera", "Lane-by-lane vehicle counts from camera video"],
    ["chart-line", "Next-minute traffic forecasts for every approach"],
    ["signal", "Signal-control research, measured in simulation"],
  ];
  return (
    <aside className={styles.brandPanel}>
      <CityBackdrop />
      <div className={styles.brandInner}>
        <div className={styles.logo}>
          <span className={styles.logoMark}><Icon name="signal" size={24} /></span>
          <span className={styles.logoText}><strong>{SITE.short}</strong><span>{SITE.model} project</span></span>
        </div>
        <div className={styles.brandCopy}>
          <p className={styles.eyebrow}>Smart city · Intelligent traffic</p>
          <h1 className={styles.brandTitle}>{SITE.title}</h1>
          <p className={styles.brandTagline}>{SITE.tagline}.</p>
        </div>
        <ul className={styles.features}>
          {features.map(([icon, text]) => (
            <li key={icon}><span className={styles.featureIcon}><Icon name={icon} size={18} /></span>{text}</li>
          ))}
        </ul>
        <p className={styles.brandFoot}><Icon name="shield-check" size={16} />Registered users only. Every page and every data request checks your session.</p>
      </div>
    </aside>
  );
}

function Notice({ kind, children }) {
  if (!children) return null;
  return (
    <div className={`${styles.notice} ${styles[kind]}`} role={kind === "error" ? "alert" : "status"}>
      <Icon name={kind === "error" ? "warning" : "check-circle"} size={18} />
      <span>{children}</span>
    </div>
  );
}

function Field({ label, error, hint, children, id }) {
  return (
    <div className={`${styles.field} ${error ? styles.fieldInvalid : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? <p className={styles.fieldError} id={`${id}-error`}>{error}</p>
        : hint ? <p className={styles.fieldHint} id={`${id}-hint`}>{hint}</p> : null}
    </div>
  );
}

const TextInput = forwardRef(function TextInput({ id, error, hint, ...rest }, ref) {
  const described = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return <input ref={ref} id={id} className={styles.input} aria-invalid={Boolean(error)} aria-describedby={described} {...rest} />;
});

function PasswordInput({ id, error, hint, ...rest }) {
  const [shown, setShown] = useState(false);
  const described = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={styles.passwordWrap}>
      <input id={id} type={shown ? "text" : "password"} className={styles.input} aria-invalid={Boolean(error)}
             aria-describedby={described} {...rest} />
      <button type="button" className={styles.reveal} onClick={() => setShown((v) => !v)}
              aria-pressed={shown} aria-controls={id}>
        <Icon name="eye" size={16} /><span>{shown ? "Hide" : "Show"}</span>
      </button>
    </div>
  );
}

function Submit({ busy, children, busyText }) {
  return (
    <button type="submit" className={styles.primary} disabled={busy} aria-busy={busy}>
      {busy ? <><span className={styles.spinner} aria-hidden="true" />{busyText}</> : <>{children}<Icon name="arrow-right" size={17} /></>}
    </button>
  );
}

function Checklist({ password, username, email }) {
  const checks = passwordChecks(password, username, email);
  return (
    <ul className={styles.checklist} aria-label="Password requirements">
      {checks.map((c) => (
        <li key={c.id} className={c.ok ? styles.met : ""}>
          <Icon name={c.ok ? "check-circle" : "x"} size={13} /><span>{c.label}</span>
          <span className={styles.srOnly}>{c.ok ? " (met)" : " (not met)"}</span>
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------ Sign in ---

function Login({ fetcher, onSignedIn, notice, unreachable, retry, prefill }) {
  const ids = useId();
  const [identifier, setIdentifier] = useState(prefill || "");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [errors, setErrors] = useState({});
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState(false);
  const first = useRef(null);
  useEffect(() => { first.current?.focus(); }, []);

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!identifier.trim()) found.identifier = "Enter your e-mail or username.";
    if (!password) found.password = "Enter your password.";
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length) return;
    setBusy(true);
    const result = await authPost("login", { identifier: identifier.trim(), password, remember }, fetcher);
    setBusy(false);
    if (result.ok && result.data.user) {
      setPassword("");
      onSignedIn(result.data.user);
      return;
    }
    setPassword("");
    setFailure(result.data.detail || "Sign-in failed. Try again.");
  };

  return (
    <form className={styles.form} onSubmit={submit} noValidate aria-labelledby={`${ids}-title`}>
      <header className={styles.formHead}>
        <h2 id={`${ids}-title`}>Sign in</h2>
        <p>Welcome back. Sign in to open the STMS console.</p>
      </header>
      {unreachable && (
        <div className={`${styles.notice} ${styles.error}`} role="alert">
          <Icon name="warning" size={18} />
          <span>The server is not answering, so nobody can sign in yet.</span>
          <button type="button" className={styles.inlineButton} onClick={retry}>Try again</button>
        </div>
      )}
      <Notice kind="success">{notice}</Notice>
      <Notice kind="error">{failure}</Notice>
      <Field label="E-mail or username" id={`${ids}-id`} error={errors.identifier}>
        <TextInput id={`${ids}-id`} ref={first} name="username" autoComplete="username" value={identifier}
                   error={errors.identifier} onChange={(e) => setIdentifier(e.target.value)} maxLength={254}
                   placeholder="you@example.org or your_username" />
      </Field>
      <Field label="Password" id={`${ids}-pw`} error={errors.password}>
        <PasswordInput id={`${ids}-pw`} name="password" autoComplete="current-password" value={password}
                       error={errors.password} onChange={(e) => setPassword(e.target.value)} maxLength={128} />
      </Field>
      <div className={styles.row}>
        <label className={styles.check}>
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          <span>Remember me for 30 days</span>
        </label>
        <a href="#forgot" className={styles.link}>Forgot password?</a>
      </div>
      <Submit busy={busy} busyText="Signing in…">Sign in</Submit>
      <p className={styles.switch}>New to STMS? <a href="#register" className={styles.link}>Create a new account</a></p>
    </form>
  );
}

// ------------------------------------------------------------------ Register ---

const TERMS = [
  "STMS is a final-year research project. It monitors and forecasts traffic and never controls a real signal.",
  "Live numbers are measurements and forecasts, not guarantees. Evaluation results are historical evidence.",
  "Your account is for you alone. Keep your password private and sign out on shared computers.",
  "We store your name, e-mail, username and a one-way hash of your password, and use them only to sign you in.",
  "Misuse, such as trying other people's accounts or probing the system, ends access.",
];

function Register({ fetcher, onRegistered }) {
  const ids = useId();
  const [form, setForm] = useState({ full_name: "", email: "", username: "", password: "", confirm_password: "" });
  const [terms, setTerms] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [errors, setErrors] = useState({});
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }));

  const validate = () => {
    const found = {};
    const name = form.full_name.trim().replace(/\s+/g, " ");
    if (name.length < 2 || name.length > 80) found.full_name = "Enter your full name (2 to 80 characters).";
    if (!EMAIL_PATTERN.test(form.email.trim())) found.email = "Enter a valid e-mail address.";
    if (!USERNAME_PATTERN.test(form.username.trim())) {
      found.username = "Use 3 to 32 letters, numbers, dots, dashes or underscores, starting with a letter.";
    }
    if (!passwordChecks(form.password, form.username.trim(), form.email.trim()).every((c) => c.ok)) {
      found.password = "The password does not meet every requirement below.";
    }
    if (!form.confirm_password || form.confirm_password !== form.password) found.confirm_password = "The passwords do not match.";
    if (!terms) found.accept_terms = "Accept the terms and conditions to continue.";
    return found;
  };

  const submit = async (event) => {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length) return;
    setBusy(true);
    const result = await authPost("register", {
      full_name: form.full_name.trim(), email: form.email.trim(), username: form.username.trim(),
      password: form.password, confirm_password: form.confirm_password, accept_terms: terms,
    }, fetcher);
    setBusy(false);
    if (result.ok) {
      setForm((f) => ({ ...f, password: "", confirm_password: "" }));
      onRegistered(result.data.user?.username || form.username.trim());
      return;
    }
    setErrors(result.data.errors || {});
    setFailure(result.data.detail || "The account was not created. Try again.");
  };

  return (
    <form className={styles.form} onSubmit={submit} noValidate aria-labelledby={`${ids}-title`}>
      <header className={styles.formHead}>
        <h2 id={`${ids}-title`}>Create your account</h2>
        <p>Register once, then sign in to reach every part of STMS.</p>
      </header>
      <Notice kind="error">{failure}</Notice>
      <Field label="Full name" id={`${ids}-name`} error={errors.full_name}>
        <TextInput id={`${ids}-name`} autoComplete="name" value={form.full_name} error={errors.full_name}
                   onChange={set("full_name")} maxLength={80} />
      </Field>
      <div className={styles.pair}>
        <Field label="E-mail" id={`${ids}-email`} error={errors.email}>
          <TextInput id={`${ids}-email`} type="email" autoComplete="email" value={form.email} error={errors.email}
                     onChange={set("email")} maxLength={254} />
        </Field>
        <Field label="Username" id={`${ids}-user`} error={errors.username} hint="Letters, numbers, . _ -">
          <TextInput id={`${ids}-user`} autoComplete="username" value={form.username} error={errors.username}
                     hint="Letters, numbers, . _ -" onChange={set("username")} maxLength={32} />
        </Field>
      </div>
      <Field label="Password" id={`${ids}-pw`} error={errors.password}>
        <PasswordInput id={`${ids}-pw`} autoComplete="new-password" value={form.password} error={errors.password}
                       onChange={set("password")} maxLength={128} />
      </Field>
      <Checklist password={form.password} username={form.username.trim()} email={form.email.trim()} />
      <Field label="Confirm password" id={`${ids}-pw2`} error={errors.confirm_password}>
        <PasswordInput id={`${ids}-pw2`} autoComplete="new-password" value={form.confirm_password}
                       error={errors.confirm_password} onChange={set("confirm_password")} maxLength={128} />
      </Field>
      <div className={`${styles.field} ${errors.accept_terms ? styles.fieldInvalid : ""}`}>
        <label className={styles.check}>
          <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)}
                 aria-invalid={Boolean(errors.accept_terms)} />
          <span>I agree to the <button type="button" className={styles.inlineLink} aria-expanded={showTerms}
                                       onClick={() => setShowTerms((v) => !v)}>terms and conditions</button></span>
        </label>
        {showTerms && (
          <ol className={styles.terms}>{TERMS.map((t) => <li key={t}>{t}</li>)}</ol>
        )}
        {errors.accept_terms && <p className={styles.fieldError}>{errors.accept_terms}</p>}
      </div>
      <Submit busy={busy} busyText="Creating account…">Create account</Submit>
      <p className={styles.switch}>Already registered? <a href="#login" className={styles.link}>Sign in</a></p>
    </form>
  );
}

// ------------------------------------------------------------------ Forgot ---

function Forgot({ fetcher }) {
  const ids = useId();
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setSent(null);
    if (!EMAIL_PATTERN.test(email.trim())) {
      setError("Enter the e-mail address you registered with.");
      return;
    }
    setError(null);
    setBusy(true);
    const result = await authPost("forgot", { email: email.trim() }, fetcher);
    setBusy(false);
    if (result.ok) setSent(result.data.message);
    else setError(result.data.detail || "The request did not go through. Try again.");
  };

  return (
    <form className={styles.form} onSubmit={submit} noValidate aria-labelledby={`${ids}-title`}>
      <header className={styles.formHead}>
        <h2 id={`${ids}-title`}>Reset your password</h2>
        <p>Enter your account's e-mail address and we will send you a link to choose a new password.</p>
      </header>
      <Notice kind="success">{sent}</Notice>
      <Field label="E-mail" id={`${ids}-email`} error={error}>
        <TextInput id={`${ids}-email`} type="email" autoComplete="email" value={email} error={error}
                   onChange={(e) => setEmail(e.target.value)} maxLength={254} />
      </Field>
      <Submit busy={busy} busyText="Sending link…">Send reset link</Submit>
      {sent && <p className={styles.small}>No e-mail server set up on this installation? The administrator finds the message in the server's outbox folder.</p>}
      <p className={styles.switch}><a href="#login" className={styles.link}>Back to sign in</a></p>
    </form>
  );
}

// ------------------------------------------------------------------ Reset ---

function Reset({ fetcher, token, onReset }) {
  const ids = useId();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState({});
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!passwordChecks(password).every((c) => c.ok)) found.password = "The password does not meet every requirement below.";
    if (!confirm || confirm !== password) found.confirm_password = "The passwords do not match.";
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length) return;
    setBusy(true);
    const result = await authPost("reset", { token, password, confirm_password: confirm }, fetcher);
    setBusy(false);
    if (result.ok) {
      // The link has done its job: AuthScreen drops it from the address and the history entry.
      onReset(result.data.message);
      return;
    }
    setErrors(result.data.errors || {});
    setFailure(result.data.errors?.token || result.data.detail || "The password was not changed.");
  };

  return (
    <form className={styles.form} onSubmit={submit} noValidate aria-labelledby={`${ids}-title`}>
      <header className={styles.formHead}>
        <h2 id={`${ids}-title`}>Choose a new password</h2>
        <p>Your reset link works once and for 30 minutes. Signing in elsewhere ends when the password changes.</p>
      </header>
      <Notice kind="error">{failure}</Notice>
      <Field label="New password" id={`${ids}-pw`} error={errors.password}>
        <PasswordInput id={`${ids}-pw`} autoComplete="new-password" value={password} error={errors.password}
                       onChange={(e) => setPassword(e.target.value)} maxLength={128} />
      </Field>
      <Checklist password={password} />
      <Field label="Confirm new password" id={`${ids}-pw2`} error={errors.confirm_password}>
        <PasswordInput id={`${ids}-pw2`} autoComplete="new-password" value={confirm} error={errors.confirm_password}
                       onChange={(e) => setConfirm(e.target.value)} maxLength={128} />
      </Field>
      <Submit busy={busy} busyText="Saving…">Save new password</Submit>
      <p className={styles.switch}><a href="#forgot" className={styles.link}>Ask for a new link</a> · <a href="#login" className={styles.link}>Sign in</a></p>
    </form>
  );
}

// ------------------------------------------------------------------ the screen ---

export function AuthScreen({ route, fetcher, onSignedIn, notice, unreachable, retry }) {
  const [message, setMessage] = useState(notice);
  const [prefill, setPrefill] = useState("");
  useEffect(() => { setMessage(notice); }, [notice]);

  let view;
  if (route.view === "register") {
    view = <Register fetcher={fetcher} onRegistered={(username) => {
      setPrefill(username);
      setMessage("Account created. Sign in with your new password to continue.");
      go("#login");
    }} />;
  } else if (route.view === "forgot") {
    view = <Forgot fetcher={fetcher} />;
  } else if (route.view === "reset") {
    view = <Reset fetcher={fetcher} token={route.token} onReset={(text) => { setMessage(text); go("#login", { replace: true }); }} />;
  } else {
    view = <Login key={prefill} fetcher={fetcher} onSignedIn={onSignedIn} notice={message} unreachable={unreachable}
                  retry={retry} prefill={prefill} />;
  }
  return (
    <div className={styles.screen} data-auth-screen={route.view}>
      <BrandPanel />
      <main className={styles.formPanel}>
        <div className={styles.card}>{view}</div>
        <p className={styles.legal}>© {new Date().getFullYear()} {SITE.title} · {SITE.institution.department}</p>
      </main>
    </div>
  );
}
