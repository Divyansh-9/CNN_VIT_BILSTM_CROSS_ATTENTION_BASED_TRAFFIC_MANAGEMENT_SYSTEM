import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PresentationVisual } from "./PresentationVisuals.jsx";
import { chapters, groups } from "./presentationContent.js";
import { Icon } from "./icons.jsx";
import { SITE } from "./site.js";
import styles from "./ExplorerTour.module.css";

const title = "STMS – Interactive Project Presentation";
const count = chapters.length;

export default function ExplorerTour({ onClose, fetcher, origin }) {
  const [index, setIndex] = useState(0);
  const [mode, setMode] = useState("guided");
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenProblem, setFullscreenProblem] = useState("");
  const dialog = useRef(null);
  const screen = useRef(null);
  const content = useRef(null);
  const heading = useRef(null);
  const chapterList = useRef(null);
  const wasFullscreen = useRef(false);
  const leavingFullscreen = useRef(false);
  const [chapter, kind, lead, details, example, source] = chapters[index];
  const group = groups.find(([, end]) => index < end)[0];

  useLayoutEffect(() => {
    const explorer = origin.trigger.closest("[data-project-explorer]");
    const previousInert = explorer.inert;
    const page = document.documentElement.style;
    const previousOverflow = page.overflow;
    explorer.inert = true;
    page.overflow = "hidden";
    return () => {
      explorer.inert = previousInert;
      page.overflow = previousOverflow;
    };
  }, [origin]);

  useLayoutEffect(() => {
    if (content.current) content.current.scrollTop = 0;
    heading.current?.focus({ preventScroll: true });
    const list = chapterList.current;
    const current = list?.querySelector('[aria-current="step"]');
    if (current) {
      const bounds = current.getBoundingClientRect();
      const viewport = list.getBoundingClientRect();
      if (bounds.top < viewport.top) list.scrollTop -= viewport.top - bounds.top;
      if (bounds.bottom > viewport.bottom) list.scrollTop += bounds.bottom - viewport.bottom;
    }
  }, [index]);

  const leave = useCallback((event) => {
    const returnToExplorer = !event?.currentTarget?.matches("a[href]");
    if (document.fullscreenElement === screen.current) {
      leavingFullscreen.current = true;
      document.exitFullscreen?.().catch(() => {});
    }
    onClose();
    if (returnToExplorer) {
      requestAnimationFrame(() => {
        origin.trigger.focus({ preventScroll: true });
        window.scrollTo?.({ left: origin.left, top: origin.top, behavior: "instant" });
      });
    }
  }, [onClose, origin]);

  useEffect(() => {
    const update = () => {
      const active = document.fullscreenElement === screen.current;
      setFullscreen(active);
      if (wasFullscreen.current && !active && !leavingFullscreen.current) leave();
      wasFullscreen.current = active;
      leavingFullscreen.current = false;
    };
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, [leave]);

  const toggleFullscreen = async () => {
    setFullscreenProblem("");
    try {
      if (fullscreen) {
        leavingFullscreen.current = true;
        await document.exitFullscreen();
      } else if (screen.current.requestFullscreen) await screen.current.requestFullscreen();
      else setFullscreenProblem("Browser fullscreen is unavailable on this device.");
    } catch {
      leavingFullscreen.current = false;
      setFullscreenProblem("The browser could not change fullscreen mode.");
    }
  };

  const move = amount => setIndex(current => Math.min(count - 1, Math.max(0, current + amount)));
  const choose = chapterIndex => { setMode("free"); setIndex(chapterIndex); };
  const keyboard = event => {
    if (event.key === "Escape") { event.preventDefault(); leave(); return; }
    if (event.key === "Tab") {
      const focusable = [...dialog.current.querySelectorAll("a[href], button:not(:disabled), select, input, summary")]
        .filter(node => node.getClientRects().length);
      const edge = event.shiftKey ? focusable[0] : focusable.at(-1);
      if (event.target === edge) {
        event.preventDefault();
        (event.shiftKey ? focusable.at(-1) : focusable[0]).focus();
      }
    }
    if (event.altKey || event.ctrlKey || event.metaKey ||
        event.target.closest?.("input, select, textarea, [contenteditable=true]")) return;
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      move(event.key === "ArrowRight" ? 1 : -1);
    }
  };

  return createPortal(<section ref={dialog} className={styles.stage} role="dialog" aria-modal="true"
    aria-labelledby="presentation-title" onKeyDown={keyboard}>
    <div ref={screen} className={styles.screen}>
      <header className={styles.header}>
        <div>
          <h1 id="presentation-title">{title}</h1>
          <p>From AI-Based Vehicle Detection to Intelligent Adaptive Traffic Signal Optimization</p>
        </div>
        <button type="button" className={styles.headerExit} aria-label="Exit Presentation" onClick={leave}>
          <Icon name="x" size={19} /><span>Exit</span>
        </button>
      </header>
      <div className={styles.body}>
        <aside className={styles.rail} aria-label="Presentation navigation">
          <div className={styles.mode} role="group" aria-label="Presentation mode">
            <button type="button" aria-pressed={mode === "guided"} onClick={() => setMode("guided")}>Guided</button>
            <button type="button" aria-pressed={mode === "free"} onClick={() => setMode("free")}>Explore Freely</button>
          </div>
          <label className={styles.chapterPicker}>Go to chapter
            <select value={index} onChange={event => choose(Number(event.target.value))}>
              {chapters.map(([name], i) => <option value={i} key={name}>{i + 1}. {name}</option>)}
            </select>
          </label>
          <nav className={styles.chapters} ref={chapterList} aria-label="Presentation chapters">
            {groups.map(([name, end], i) => {
              const start = groups[i - 1]?.[1] ?? 0;
              return <section key={name}>
                <h2>{name}</h2>
                <ol start={start + 1}>
                  {chapters.slice(start, end).map(([name], offset) => {
                    const number = start + offset;
                    return <li key={name}><button type="button" onClick={() => choose(number)}
                      aria-current={number === index ? "step" : undefined}>
                      <span aria-hidden="true">{String(number + 1).padStart(2, "0")}</span>{name}
                    </button></li>;
                  })}
                </ol>
              </section>;
            })}
          </nav>
        </aside>
        <main ref={content} className={styles.content}>
          <article key={index} className={styles.slide}>
            <p className={styles.groupName}>{group}</p>
            <h2 ref={heading} tabIndex={-1}>{chapter}</h2>
            <p className={styles.lead}>{lead}</p>
            <ul className={styles.explainer}>{details.map(line => <li key={line}>{line}</li>)}</ul>
            <PresentationVisual key={kind} kind={kind} fetcher={fetcher} />
            <p className={styles.example}>{example}</p>
            <details className={styles.technical}><summary>Project source</summary>
              <a href={`${SITE.repository}/blob/main/${source}`} target="_blank" rel="noreferrer">{source}</a>
            </details>
            {index === count - 1 && <div className={styles.actions}>
              <a className={styles.primary} href="#overview" onClick={leave}>Launch STMS Dashboard</a>
              <a className={styles.secondary} href="#explore/architecture" onClick={leave}>Explore Technical Architecture</a>
              <button className={styles.secondary} type="button" onClick={leave}>Exit Presentation</button>
            </div>}
          </article>
        </main>
      </div>
      <footer className={styles.footer}>
        <button className={styles.secondary} type="button" onClick={() => move(-1)} disabled={!index}>Previous</button>
        <div className={styles.progress}>
          <span role="status">Chapter {index + 1} of {count}</span>
          <progress aria-label="Presentation progress" value={index + 1} max={count} />
        </div>
        <button className={styles.primary} type="button" onClick={index === count - 1 ? leave : () => move(1)}>
          {index === count - 1 ? "Finish" : "Next"}
        </button>
        <button className={styles.secondary} type="button" onClick={toggleFullscreen}>
          {fullscreen ? "Exit Fullscreen" : "Fullscreen"}
        </button>
        {fullscreenProblem && <p role="status" className={styles.fullscreenProblem}>{fullscreenProblem}</p>}
      </footer>
    </div>
  </section>, document.body);
}
