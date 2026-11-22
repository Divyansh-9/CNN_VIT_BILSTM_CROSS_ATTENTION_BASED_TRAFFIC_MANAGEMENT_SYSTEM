// The sign-in gate (AuthGate.jsx) and its screens (Auth.jsx), against a fake server.
// The real server's rules are tested in tests/test_auth.py; here: nothing of the
// project renders until /auth/me names a user, and every way out ends at sign-in.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AccountMenu, AuthGate, authRoute } from "./AuthGate.jsx";
import { SIGNED_OUT_EVENT, passwordChecks } from "./auth.js";
import { get } from "./api.js";

window.scrollTo = () => {};
afterEach(() => { cleanup(); window.history.replaceState(null, "", "/"); });

const USER = { id: 1, full_name: "Asha Rao", email: "asha@example.org", username: "asha_r" };
const GOOD = "Signal-Green-42!";

// A fake /auth server: `signedIn` decides /auth/me; POSTs answer from `answers`.
function server({ signedIn = false, answers = {}, down = false } = {}) {
  const state = { signedIn, calls: [] };
  const reply = (status, data) => ({ ok: status < 300, status, json: async () => data });
  state.fetcher = async (path, init = {}) => {
    state.calls.push({ path, method: init.method, body: init.body ? JSON.parse(init.body) : undefined });
    if (down) throw new Error("connection refused");
    if (path === "/auth/me") return state.signedIn ? reply(200, { user: USER }) : reply(401, { detail: "sign in required" });
    const action = path.replace("/auth/", "");
    if (action === "logout") { state.signedIn = false; return reply(200, { signed_out: true }); }
    const answer = answers[action];
    if (typeof answer === "function") return answer(JSON.parse(init.body), state, reply);
    return answer ? reply(...answer) : reply(404, { detail: "not found" });
  };
  return state;
}

const Project = () => <div data-testid="project">STMS project <AccountMenu /></div>;
const type = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("the gate", () => {
  it("shows nothing of the project while it checks, and the sign-in screen when signed out", async () => {
    const fake = server();
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    expect(screen.getByRole("status").textContent).toMatch(/Checking your session/);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(screen.queryByTestId("project")).toBeNull();
  });

  it("shows the sign-in screen whatever page the address names", async () => {
    for (const hash of ["#live", "#overview", "#explore", "#results", "#home"]) {
      window.location.hash = hash;
      const fake = server();
      render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
      expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
      expect(screen.queryByTestId("project")).toBeNull();
      cleanup();
    }
  });

  it("opens the project for a signed-in session", async () => {
    const fake = server({ signedIn: true });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    expect(await screen.findByTestId("project")).toBeTruthy();
    expect(screen.getByRole("button", { name: /asha_r/ })).toBeTruthy();
  });

  it("signs in, then goes to the STMS home page", async () => {
    window.location.hash = "#live";
    const fake = server({ answers: { login: (body, s, reply) => {
      if (body.password !== GOOD) return reply(401, { detail: "The e-mail, username or password is not correct." });
      s.signedIn = true;
      return reply(200, { user: USER });
    } } });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Sign in" });
    type("E-mail or username", "asha_r");
    type("Password", "wrong-one");
    fireEvent.click(screen.getByRole("button", { name: /^Sign in/ }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/not correct/);
    expect(screen.getByLabelText("Password").value).toBe("");          // never kept after a failure
    type("Password", GOOD);
    fireEvent.click(screen.getByRole("checkbox", { name: /Remember me/ }));
    fireEvent.click(screen.getByRole("button", { name: /^Sign in/ }));
    expect(await screen.findByTestId("project")).toBeTruthy();
    expect(window.location.hash).toBe("#home");
    expect(fake.calls.find((c) => c.path === "/auth/login" && c.body.password === GOOD).body.remember).toBe(true);
  });

  it("says what is missing before asking the server", async () => {
    const fake = server();
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Sign in" });
    fireEvent.click(screen.getByRole("button", { name: /^Sign in/ }));
    expect(screen.getByText("Enter your e-mail or username.")).toBeTruthy();
    expect(screen.getByText("Enter your password.")).toBeTruthy();
    expect(fake.calls.some((c) => c.path === "/auth/login")).toBe(false);
  });

  it("shows and hides the password", async () => {
    render(<AuthGate fetcher={server().fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Sign in" });
    const field = screen.getByLabelText("Password");
    expect(field.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(field.type).toBe("text");
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(field.type).toBe("password");
  });

  it("signs out to the sign-in screen, and Back does not bring the project back", async () => {
    window.location.hash = "#live";
    const fake = server({ signedIn: true });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByTestId("project");
    fireEvent.click(screen.getByRole("button", { name: /asha_r/ }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Sign out/ }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(screen.getByText("You have signed out.")).toBeTruthy();
    expect(window.location.hash).toBe("#login");
    expect(fake.calls.some((c) => c.path === "/auth/logout" && c.method === "POST")).toBe(true);
    await act(async () => { window.location.hash = "#live"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(screen.queryByTestId("project")).toBeNull();
  });

  it("ends at sign-in when any data read finds the session expired", async () => {
    const fake = server({ signedIn: true });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByTestId("project");
    const read = await get("/evidence", async () => ({ ok: false, status: 401, json: async () => ({}) }));
    expect(read).toEqual({ status: "error", reason: "signed out" });
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(screen.getByText(/session has ended/)).toBeTruthy();
    expect(screen.queryByTestId("project")).toBeNull();
  });

  it("ends at sign-in on the signed-out event from any tab or client", async () => {
    render(<AuthGate fetcher={server({ signedIn: true }).fetcher}><Project /></AuthGate>);
    await screen.findByTestId("project");
    act(() => { window.dispatchEvent(new CustomEvent(SIGNED_OUT_EVENT)); });
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
  });

  it("says when the server cannot be reached, and offers to try again", async () => {
    render(<AuthGate fetcher={server({ down: true }).fetcher}><Project /></AuthGate>);
    expect(await screen.findByText(/server is not answering/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(screen.queryByTestId("project")).toBeNull();
  });
});

describe("registration", () => {
  const fill = (overrides = {}) => {
    const v = { name: "Asha Rao", email: "asha@example.org", user: "asha_r", pw: GOOD, pw2: GOOD, ...overrides };
    type("Full name", v.name);
    type("E-mail", v.email);
    type("Username", v.user);
    type("Password", v.pw);
    type("Confirm password", v.pw2);
  };

  it("checks every field before sending, including terms and a matching confirmation", async () => {
    window.location.hash = "#register";
    const fake = server();
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Create your account" });
    fill({ email: "nope", user: "1x", pw: "short", pw2: "other" });
    fireEvent.click(screen.getByRole("button", { name: /Create account/ }));
    expect(screen.getByText("Enter a valid e-mail address.")).toBeTruthy();
    expect(screen.getByText(/Use 3 to 32 letters/)).toBeTruthy();
    expect(screen.getByText(/does not meet every requirement/)).toBeTruthy();
    expect(screen.getByText("The passwords do not match.")).toBeTruthy();
    expect(screen.getByText("Accept the terms and conditions to continue.")).toBeTruthy();
    expect(fake.calls.some((c) => c.path === "/auth/register")).toBe(false);
  });

  it("shows the server's answer for a taken e-mail or username by field", async () => {
    window.location.hash = "#register";
    const fake = server({ answers: { register: [422, { detail: "Check the highlighted fields.",
      errors: { email: "An account with this e-mail already exists.", username: "This username is taken." } }] } });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Create your account" });
    fill();
    fireEvent.click(screen.getByRole("checkbox", { name: /I agree/ }));
    fireEvent.click(screen.getByRole("button", { name: /Create account/ }));
    expect(await screen.findByText("An account with this e-mail already exists.")).toBeTruthy();
    expect(screen.getByText("This username is taken.")).toBeTruthy();
  });

  it("confirms a new account and sends it to sign-in with the username filled in", async () => {
    window.location.hash = "#register";
    const fake = server({ answers: { register: [201, { user: USER, message: "Account created." }] } });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Create your account" });
    fill();
    fireEvent.click(screen.getByRole("button", { name: "terms and conditions" }));
    expect(screen.getByText(/never controls a real signal/)).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: /I agree/ }));
    fireEvent.click(screen.getByRole("button", { name: /Create account/ }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(screen.getByText(/Account created/)).toBeTruthy();
    expect(screen.getByLabelText("E-mail or username").value).toBe("asha_r");
    expect(screen.queryByTestId("project")).toBeNull();               // registering does not sign in
    expect(fake.calls.find((c) => c.path === "/auth/register").body).toEqual({
      full_name: "Asha Rao", email: "asha@example.org", username: "asha_r", password: GOOD,
      confirm_password: GOOD, accept_terms: true });
  });

  it("lists the password rules the server enforces", () => {
    const failed = (pw, u, e) => passwordChecks(pw, u, e).filter((c) => !c.ok).map((c) => c.id);
    expect(failed(GOOD, "asha_r", "asha@example.org")).toEqual([]);
    expect(failed("short", "", "")).toEqual(["length", "upper", "digit", "symbol"]);
    expect(failed("Password-12345", "", "")).toEqual(["common"]);
    expect(failed("Asha_r-is-1-ok", "asha_r", "")).toEqual(["personal"]);
  });
});

describe("password reset", () => {
  it("answers a reset request the same way for any address", async () => {
    window.location.hash = "#forgot";
    const fake = server({ answers: { forgot: [202, { message: "If an account uses that address, a reset link is on its way." }] } });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Reset your password" });
    type("E-mail", "asha@example.org");
    fireEvent.click(screen.getByRole("button", { name: /Send reset link/ }));
    expect(await screen.findByText(/a reset link is on its way/)).toBeTruthy();
  });

  it("sets a new password from a reset link, then asks to sign in", async () => {
    const token = "a".repeat(43);
    window.location.hash = `#reset/${token}`;
    const fake = server({ answers: { reset: [200, { message: "Password changed. Sign in with your new password." }] } });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await screen.findByRole("heading", { name: "Choose a new password" });
    type("New password", "Amber-Phase-77#");
    type("Confirm new password", "Amber-Phase-77#");
    fireEvent.click(screen.getByRole("button", { name: /Save new password/ }));
    expect(await screen.findByText(/Password changed/)).toBeTruthy();
    expect(window.location.hash).toBe("#login");
    expect(fake.calls.find((c) => c.path === "/auth/reset").body.token).toBe(token);
  });

  it("routes only well-formed reset links", () => {
    expect(authRoute(`#reset/${"x".repeat(43)}`)).toEqual({ view: "reset", token: "x".repeat(43) });
    expect(authRoute("#reset/short")).toEqual({ view: "login" });
    expect(authRoute("#register")).toEqual({ view: "register" });
    expect(authRoute("#anything")).toEqual({ view: "login" });
  });
});

describe("outside the gate", () => {
  it("the account menu renders nothing, so pages tested alone are unchanged", () => {
    const { container } = render(<AccountMenu />);
    expect(container.innerHTML).toBe("");
  });

  it("keeps nothing about the session in browser storage", async () => {
    window.localStorage.clear();
    const fake = server({ signedIn: true });
    render(<AuthGate fetcher={fake.fetcher}><Project /></AuthGate>);
    await waitFor(() => expect(screen.getByTestId("project")).toBeTruthy());
    const stored = JSON.stringify({ ...window.localStorage, ...window.sessionStorage });
    expect(stored).not.toMatch(/asha|session|token/i);
  });
});
