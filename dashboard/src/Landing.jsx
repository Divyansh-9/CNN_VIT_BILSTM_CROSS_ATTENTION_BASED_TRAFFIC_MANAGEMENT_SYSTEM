import { useState } from "react";
import { Icon } from "./icons.jsx";
import styles from "./Landing.module.css";
import { SITE, asset } from "./site.js";
import { ThemeSwitch } from "./ThemeSwitch.jsx";
import { AccountMenu } from "./AuthGate.jsx";

// The project's front door. It introduces the work and sends a visitor one of
// two ways: to learn how it works (#explore) or to operate it (#overview).
// It polls nothing and shows no live number, so nothing here can be mistaken
// for a reading (ADR-014). The results quoted are the committed ones, in the
// wording docs/TEAM-STATUS.md says is safe to repeat.

const HIGHLIGHTS = [
  { icon: "video-camera", title: "Lane-level counting from a camera",
    text: "A YOLO detector finds vehicles in one frame every 2 seconds, and each is assigned to the nearest hand-placed lane centre." },
  { icon: "chart-line", title: "Two forecasts per approach",
    text: "For the next 60 seconds: a congestion level (LOW, MEDIUM or HIGH) and an expected vehicle count, published separately." },
  { icon: "plugs", title: "Edge to dashboard, end to end",
    text: "Edge node → MQTT → FastAPI server with SQLite → this read-only dashboard, refreshed every 2 seconds." },
  { icon: "shield-check", title: "Private by design",
    text: "Video frames never leave the edge device. Only counts and forecasts cross the network." },
  { icon: "brain", title: "MFSTNet vision model",
    text: "ResNet-50 and DINOv2 ViT features fused by gated cross-attention, then a BiLSTM, evaluated camera by camera." },
  { icon: "flask", title: "Signal-control research",
    text: "PPO reinforcement learning on a SUMO intersection, compared against tuned Webster timing, in simulation only." },
];

const STACK = [
  { group: "Vision and learning", items: ["Python", "PyTorch", "Ultralytics YOLOv8", "ResNet-50", "DINOv2 ViT-S/14", "ONNX Runtime"] },
  { group: "Simulation and control", items: ["SUMO 1.27", "Stable-Baselines3 PPO", "Gymnasium", "Webster baseline"] },
  { group: "System", items: ["MQTT (Mosquitto)", "FastAPI", "SQLite", "Docker Compose"] },
  { group: "Interface", items: ["React 18", "Vite", "CSS Modules"] },
];

const OUTCOMES = [
  { verdict: "Supported", kind: "yes", title: "Next-minute count forecast",
    text: "On held-out cameras the ridge model's error was 0.748 vehicles, against 0.972 for repeating the last minute (difference 0.224, 95% CI 0.181–0.271)." },
  { verdict: "Not shown", kind: "open", title: "Vision model MFSTNet",
    text: "On four foreign cameras the full model could not be told apart from a simple linear probe." },
  { verdict: "Null result", kind: "open", title: "Forecasts for signal control",
    text: "No demonstrated control benefit from forecasts under the tested conditions." },
];

const FACTS = [
  ["60 s", "forecast horizon"],
  ["2 s", "between counted frames"],
  ["4", "approaches per intersection"],
  ["0.748", "vehicles mean error, next minute"],
];

function Brand() {
  return (
    <a className={styles.brand} href="#home" aria-label={`${SITE.short} home`}>
      <span className={styles.mark}><Icon name="signal" size={20} /></span>
      <span>{SITE.short}</span>
    </a>
  );
}

function HeroBackdrop() {
  if (SITE.campusPhoto) {
    return <div className={styles.photo} style={{ backgroundImage: `url("${asset(SITE.campusPhoto)}")` }} aria-hidden="true" />;
  }
  // No campus photograph yet: an abstract intersection, drawn, not a picture of traffic.
  return (
    <div className={styles.drawn} aria-hidden="true" data-placeholder="campus-photo">
      <svg viewBox="0 0 1200 700" preserveAspectRatio="xMidYMid slice" className={styles.city}>
        <rect className={styles.road} x="0" y="300" width="1200" height="100" />
        <rect className={styles.road} x="700" y="0" width="100" height="700" />
        <line className={styles.lane} x1="0" y1="350" x2="1200" y2="350" />
        <line className={styles.lane} x1="750" y1="0" x2="750" y2="700" />
        <circle className={styles.ring} cx="750" cy="350" r="120" />
        <circle className={styles.ring2} cx="750" cy="350" r="200" />
        <rect className={`${styles.car} ${styles.carE}`} x="-40" y="318" width="34" height="14" rx="4" />
        <rect className={`${styles.car} ${styles.carW}`} x="1200" y="368" width="34" height="14" rx="4" />
        <rect className={`${styles.car} ${styles.carS}`} x="718" y="-40" width="14" height="34" rx="4" />
      </svg>
    </div>
  );
}

const TRAFFIC_DIRECTIONS = [["east", "E"], ["west", "W"], ["north", "N"], ["south", "S"]];
const TRAFFIC_QUEUE = ["car", "truck", "bike", "car"];

function IntersectionAnimation() {
  const [paused, setPaused] = useState(false);
  return (
    <figure className={styles.heroTraffic} data-traffic-paused={paused}>
      <div className={styles.trafficScene} aria-hidden="true">
        <div className={styles.roadAcross} />
        <div className={styles.roadDown} />
        <div className={styles.crossing} data-edge="top" />
        <div className={styles.crossing} data-edge="bottom" />
        <div className={styles.crossing} data-edge="left" />
        <div className={styles.crossing} data-edge="right" />
        {TRAFFIC_DIRECTIONS.map(([direction, label]) => (
          <div className={styles.signalBox} key={direction} data-signal={direction}>
            <b>{label}</b>
            <span className={styles.signalLamp} data-lamp="red" />
            <span className={styles.signalLamp} data-lamp="amber" />
            <span className={styles.signalLamp} data-lamp="green" />
          </div>
        ))}
        {TRAFFIC_DIRECTIONS.map(([direction]) => (
          <div className={styles.trafficTrack} key={direction} data-direction={direction}>
            {TRAFFIC_QUEUE.map((vehicle, index) => (
              <span className={styles.vehicleMotion} key={index} style={{ "--queue-index": index }}>
                <span className={styles.toyVehicle} data-vehicle={vehicle}>
                  <span />
                </span>
              </span>
            ))}
          </div>
        ))}
      </div>
      <figcaption>
        <span><Icon name="signal" size={16} /> Intersection signal demo</span>
        <button type="button" className={styles.motionButton} onClick={() => setPaused((value) => !value)}>
          {paused ? "Resume" : "Pause"}<span className={styles.srOnly}> traffic animation</span>
        </button>
      </figcaption>
    </figure>
  );
}

function Member({ member, index }) {
  const named = Boolean(member.name);
  return (
    <article className={styles.member} data-placeholder={named ? undefined : "team-member"}>
      <div className={styles.portrait}>
        {member.photo
          ? <img src={asset(member.photo)} alt={member.name ?? `Team member ${index + 1}`}
            style={{ objectPosition: member.photoPosition }} />
          : <div className={styles.noPhoto}><Icon name="user" size={40} /><span>Photo to be added</span></div>}
      </div>
      <div className={styles.memberBody}>
        <p className={styles.memberMeta}>
          {member.lead && <span className={styles.lead}>Team Leader</span>}
          {member.section && <span>Section {member.section}</span>}
        </p>
        <h3>{member.name ?? `Team member ${index + 1}`}</h3>
        <p className={styles.role}>{member.role || "Role to be added in dashboard/src/site.js"}</p>
        {(member.linkedin || member.github) && (
          <p className={styles.links}>
            {member.linkedin && <a href={member.linkedin} target="_blank" rel="noreferrer"><Icon name="linkedin-logo" size={16} />LinkedIn</a>}
            {member.github && <a href={member.github} target="_blank" rel="noreferrer"><Icon name="github-logo" size={16} />GitHub</a>}
          </p>
        )}
      </div>
    </article>
  );
}

export function Landing({ redesign }) {
  const inst = SITE.institution;
  return (
    <div className={`${styles.page} ${redesign ? styles.redesign : ""}`}>
      <header className={styles.bar}>
        <Brand />
        <div className={styles.barTools}>
          <ThemeSwitch />
          <AccountMenu />
          <nav aria-label="Main" className={styles.barNav}>
            <a href="#explore">Explore the project</a>
            <a href="#overview" className={styles.barCta}>Launch Dashboard<Icon name="arrow-right" size={16} /></a>
          </nav>
        </div>
      </header>

      <section className={styles.hero} aria-labelledby="heroTitle">
        {redesign ? <IntersectionAnimation /> : <HeroBackdrop />}
        <div className={styles.heroInner}>
          {!redesign && <p className={styles.badge}>Smart city technology <span aria-hidden="true">|</span> Intelligent traffic management</p>}
          <h1 id="heroTitle" className={styles.title}>{SITE.title}</h1>
          {!redesign && <p className={styles.tagline}>{SITE.tagline}</p>}
          <p className={styles.lede}>{redesign
            ? "STMS counts vehicles by approach and forecasts congestion for the next 60 seconds."
            : SITE.description}</p>
          <div className={styles.ctas}>
            <a className={styles.cta} href="#explore" data-cta="explore">
              <span className={styles.ctaIcon}><Icon name="compass" size={26} /></span>
              <span className={styles.ctaText}>
                <strong>Explore the project</strong>
                <span>{redesign ? "Follow a camera frame through five technical steps." : "The architecture, technologies, workflow and algorithms, explained step by step."}</span>
              </span>
              <Icon name="arrow-right" size={20} />
            </a>
            <a className={`${styles.cta} ${styles.ctaPrimary}`} href="#overview" data-cta="launch">
              <span className={styles.ctaIcon}><Icon name="rocket-launch" size={26} /></span>
              <span className={styles.ctaText}>
                <strong>Launch Dashboard</strong>
                <span>{redesign ? "Analyze a traffic recording, open Live, or try the guided replay." : "The operational dashboard: live monitoring, video analysis, analytics and results."}</span>
              </span>
              <Icon name="arrow-right" size={20} />
            </a>
          </div>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="teamTitle">
        {!redesign && <p className={styles.kicker}>Our team</p>}
        <h2 id="teamTitle" className={styles.h2}>The people behind {SITE.short}</h2>
        <div className={styles.team}>
          {SITE.team.slice(0, 4).map((m, i) => <Member key={i} member={m} index={i} />)}
        </div>
        <dl className={styles.facts}>
          {FACTS.map(([n, label]) => (
            <div key={label}><dt>{n}</dt><dd>{label}</dd></div>
          ))}
        </dl>
      </section>

      <section className={`${styles.section} ${styles.split}`} aria-label="Problem and objective">
        <div className={styles.panel}>
          <p className={styles.kicker}><Icon name="warning" size={16} />The problem</p>
          <h2 className={styles.h3}>Fixed timers cannot see the queue</h2>
          <p>
            Most signals run fixed cycles that ignore the traffic actually waiting. Indian intersections add mixed
            vehicles, two-wheelers filtering between lanes and little lane discipline, which defeats loop detectors
            and methods built for orderly traffic.
          </p>
        </div>
        <div className={styles.panel}>
          <p className={styles.kicker}><Icon name="target" size={16} />Our objective</p>
          <h2 className={styles.h3}>Measure first, then forecast</h2>
          <p>
            Use an ordinary fixed camera to count vehicles on each approach, forecast the next minute of traffic, and
            test in simulation whether those forecasts help a learned signal controller, reporting what the
            measurements show, including what they do not.
          </p>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="hlTitle">
        <p className={styles.kicker}>Key highlights</p>
        <h2 id="hlTitle" className={styles.h2}>What is built</h2>
        <div className={styles.cards}>
          {HIGHLIGHTS.map((h) => (
            <article key={h.title} className={styles.card}>
              <span className={styles.cardIcon}><Icon name={h.icon} size={22} /></span>
              <h3>{h.title}</h3>
              <p>{h.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.section} aria-labelledby="stackTitle">
        <p className={styles.kicker}>Technologies used</p>
        <h2 id="stackTitle" className={styles.h2}>The stack</h2>
        <div className={styles.stack}>
          {STACK.map((s) => (
            <div key={s.group} className={styles.stackGroup}>
              <h3>{s.group}</h3>
              <ul>{s.items.map((t) => <li key={t}>{t}</li>)}</ul>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section} aria-labelledby="outTitle">
        <p className={styles.kicker}>Project outcomes</p>
        <h2 id="outTitle" className={styles.h2}>What the measurements showed</h2>
        <div className={styles.outcomes}>
          {OUTCOMES.map((o) => (
            <article key={o.title} className={styles.outcome} data-verdict={o.kind}>
              <p className={styles.verdict}><Icon name={o.kind === "yes" ? "check-circle" : "scales"} size={16} />{o.verdict}</p>
              <h3>{o.title}</h3>
              <p>{o.text}</p>
            </article>
          ))}
        </div>
        <p className={styles.note}>
          Not yet shown: results on Indian footage (every evaluation camera is foreign), accuracy against human counts,
          and performance on a live camera. The system forecasts traffic; it does not control physical signals.
        </p>
      </section>

      <section className={`${styles.section} ${styles.final}`} aria-label="Get started">
        <h2 className={styles.h2}>Ready to look inside?</h2>
        <div className={styles.finalCtas}>
          <a className={styles.button} href="#explore"><Icon name="compass" size={18} />Explore the project</a>
          <a className={`${styles.button} ${styles.buttonPrimary}`} href="#overview"><Icon name="rocket-launch" size={18} />Launch Dashboard</a>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={`${styles.institution} ${inst.logo ? styles.institutionWordmark : ""}`} data-placeholder={inst.name ? undefined : "institution"}>
          {inst.logo
            ? <img src={asset(inst.logo)} alt={inst.name ?? "Institution logo"} className={styles.logo} />
            : <span className={styles.logoBox}><Icon name="graduation-cap" size={22} /></span>}
          <div>
            {!inst.logo && <strong>{inst.name ?? "Institution name to be added"}</strong>}
            <span>{inst.department}</span>
          </div>
        </div>
        <p className={styles.footNote}>
          {SITE.title} · {SITE.model} · B.Tech CSE (ML/AI) major project
          {SITE.repository && <> · <a href={SITE.repository} target="_blank" rel="noreferrer"><Icon name="github-logo" size={14} />Source code</a></>}
        </p>
      </footer>
    </div>
  );
}
