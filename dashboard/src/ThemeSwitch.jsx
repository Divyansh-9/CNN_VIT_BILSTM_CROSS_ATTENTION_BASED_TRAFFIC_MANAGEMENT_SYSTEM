import { useState } from "react";
import { Icon } from "./icons.jsx";
import { THEMES, saveTheme, storedTheme } from "./theme.js";
import styles from "./ThemeSwitch.module.css";

// Dark / System / Light, as one control. `compact` hides the words on narrow bars.
export function ThemeSwitch({ compact = false }) {
  const [choice, setChoice] = useState(storedTheme);
  const pick = (k) => { setChoice(k); saveTheme(k); };
  return (
    <div className={`${styles.switch} ${compact ? styles.compact : ""}`} role="group" aria-label="Colour theme" data-theme-switch="true">
      {THEMES.map(([key, label, icon]) => (
        <button key={key} type="button" aria-pressed={choice === key} onClick={() => pick(key)}
                title={`${label} theme`} data-theme-choice={key}>
          <Icon name={icon} size={15} /><span>{label}</span>
        </button>
      ))}
    </div>
  );
}
