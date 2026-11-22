// Dark, System or Light (D18's approved Light mode). The choice only sets
// data-theme on <html>; every colour comes from theme.css, where each theme's
// values are measured by tokens.test.js. "system" removes the attribute, so the
// operating system's light/dark preference decides. A theme never changes
// meaning: the same text renders in every theme, and every class keeps its
// label and shape.

export const THEMES = [["dark", "Dark", "moon"], ["system", "System", "desktop"], ["light", "Light", "sun"]];
const KEY = "stms.theme";
const BAR = { dark: "#080808", light: "#f6f4f1" };

export function storedTheme() {
  try {
    const v = window.localStorage.getItem(KEY);
    return THEMES.some(([k]) => k === v) ? v : "system";
  } catch {
    return "system"; // storage blocked: follow the system, and do not remember
  }
}

export function applyTheme(choice, root = document.documentElement) {
  if (choice === "dark" || choice === "light") root.dataset.theme = choice;
  else delete root.dataset.theme;
  const resolved = choice === "system"
    ? (window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark")
    : choice;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", BAR[resolved]);
}

export function saveTheme(choice) {
  try { window.localStorage.setItem(KEY, choice); } catch { /* a convenience only */ }
  applyTheme(choice);
}
