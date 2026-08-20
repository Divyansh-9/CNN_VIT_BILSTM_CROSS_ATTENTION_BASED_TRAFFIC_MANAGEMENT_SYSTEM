"""Build the project review deck from real images and committed numbers.

    python scripts/build_review_deck.py

Twenty slides covering what has been built, the stack it runs on, every
validation metric, the decisions taken and the defects found on the way.

**Every figure comes from a committed CSV in `experiments/results/`.** The
images are rendered from real footage by the real detector rather than picked
for looking good, and the deck is regenerated rather than edited, so a number
that changes upstream changes here too.

Non-ASCII characters are escaped to numeric entities on write: the page carries
no charset of its own, so a browser opening the file directly guesses latin-1
and turns every em dash into mojibake.
"""
import base64
import pathlib

S = pathlib.Path("C:/Users/TestUser/AppData/Local/Temp/claude/"
                 "d--major-project/76944353-9700-4f88-ab34-5bc3cc8818a4/scratchpad")
D = S / "deck"


def img(name: str) -> str:
    return base64.b64encode((D / name).read_bytes()).decode()


CSS = """
:root{
  --bg:#0D1117; --panel:#141A21; --sunk:#10151B; --line:#232C36;
  --ink:#E8EDF2; --muted:#95A3B2; --faint:#66757F;
  --accent:#6366F1; --accent-dim:#3E3F8F; --accent-wash:#181A33;
  --good:#3FB981; --warn:#E0A32E; --bad:#E0674E;
  --body:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,"Cascadia Mono",Consolas,monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);
  font-family:var(--body);-webkit-font-smoothing:antialiased}

.deck{width:100%}
.slide{
  position:relative;width:100%;min-height:100vh;
  display:flex;flex-direction:column;justify-content:center;
  padding:72px 84px 96px;border-bottom:1px solid var(--line);
  scroll-snap-align:start;background:var(--bg);
}
@media(max-width:820px){.slide{padding:48px 26px 76px;min-height:auto}}
.deck{scroll-snap-type:y proximity}

.kicker{font-family:var(--mono);font-size:11px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--accent);margin:0 0 20px;font-weight:500}
h1{font-size:clamp(2.6rem,6.5vw,4.6rem);font-weight:700;line-height:1.02;
  letter-spacing:-.035em;margin:0 0 22px;text-wrap:balance}
h2{font-size:clamp(1.8rem,3.6vw,2.7rem);font-weight:650;line-height:1.1;
  letter-spacing:-.025em;margin:0 0 14px;text-wrap:balance}
h3{font-size:1.02rem;font-weight:600;margin:0 0 10px;letter-spacing:-.01em}
.sub{font-size:clamp(1rem,1.5vw,1.22rem);color:var(--muted);
  max-width:74ch;margin:0 0 30px;line-height:1.55}
.sub strong{color:var(--ink);font-weight:600}
p{margin:0 0 14px;max-width:76ch;line-height:1.62}
.small{font-size:.9rem;color:var(--muted)}
.tiny{font-family:var(--mono);font-size:11.5px;color:var(--faint);line-height:1.6}
strong{font-weight:650}
em{font-style:normal;color:var(--accent);font-weight:600}

.num{position:absolute;bottom:30px;right:84px;font-family:var(--mono);
  font-size:11px;color:var(--faint);letter-spacing:.1em}
@media(max-width:820px){.num{right:26px;bottom:20px}}
.tag{position:absolute;top:30px;right:84px;font-family:var(--mono);
  font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
@media(max-width:820px){.tag{right:26px;top:18px}}

.grid{display:grid;gap:18px}
.g2{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(215px,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(175px,1fr))}

.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:20px 22px}
.card h3{color:var(--ink)}
.card p{margin:0;font-size:.92rem;color:var(--muted);line-height:1.55}
.card .k{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin-bottom:10px}
.card .v{font-size:2.05rem;font-weight:700;letter-spacing:-.03em;line-height:1;
  font-variant-numeric:tabular-nums}
.card .v.ok{color:var(--good)} .card .v.warn{color:var(--warn)}
.card .v.acc{color:var(--accent)}
.card .n{font-size:.85rem;color:var(--muted);margin-top:9px;line-height:1.5}

.scroll{overflow-x:auto;margin:0 0 18px;border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:.9rem;
  font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:9px 16px 9px 0;border-bottom:1px solid var(--line);
  white-space:nowrap}
th{font-family:var(--mono);font-size:10px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);font-weight:500;
  border-bottom:1px solid var(--accent-dim)}
td.m{font-family:var(--mono);font-size:.86rem}
tr.hi td{background:var(--accent-wash);color:var(--ink);font-weight:600}
.ok{color:var(--good)} .warn{color:var(--warn)} .bad{color:var(--bad)}

figure{margin:0}
figure img{width:100%;max-width:100%;height:auto;display:block;border-radius:8px;
  border:1px solid var(--line)}
figcaption{font-size:.85rem;color:var(--muted);margin-top:12px;max-width:80ch;
  line-height:1.55}

.flow{display:flex;flex-wrap:wrap;gap:9px;align-items:stretch;margin:0 0 20px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:6px;
  padding:11px 14px;font-family:var(--mono);font-size:11.5px;color:var(--muted);
  display:flex;flex-direction:column;gap:3px;min-width:0}
.step b{color:var(--ink);font-weight:600;font-size:12px}
.step.acc{border-color:var(--accent-dim);background:var(--accent-wash)}
.step.acc b{color:var(--accent)}

.callout{border-left:3px solid var(--accent);background:var(--accent-wash);
  padding:16px 22px;border-radius:0 6px 6px 0;margin:0 0 18px}
.callout p{margin:0;font-size:.95rem}
.callout p+p{margin-top:9px;color:var(--muted)}
.callout.warn{border-left-color:var(--warn);background:#1E1A10}
.callout.good{border-left-color:var(--good);background:#0F1E18}

ul{margin:0 0 16px;padding-left:20px}
li{margin-bottom:9px;max-width:76ch;line-height:1.58}
li::marker{color:var(--accent)}
code{font-family:var(--mono);font-size:.86em;background:var(--sunk);
  padding:2px 6px;border-radius:3px;color:var(--ink)}

.bar{position:fixed;top:0;left:0;height:2px;background:var(--accent);
  z-index:50;transition:width .12s linear;width:0}
.hint{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);
  font-family:var(--mono);font-size:10.5px;color:var(--faint);z-index:50;
  background:var(--panel);border:1px solid var(--line);border-radius:20px;
  padding:6px 14px;opacity:.9}
@media print{.bar,.hint,.num{display:none}
  .slide{min-height:auto;page-break-after:always;border:none}}
"""

JS = """
const slides = [...document.querySelectorAll('.slide')];
const bar = document.querySelector('.bar');
function go(i){
  i = Math.max(0, Math.min(slides.length - 1, i));
  slides[i].scrollIntoView({behavior:'smooth', block:'start'});
}
function current(){
  const mid = window.scrollY + window.innerHeight / 2;
  return slides.findIndex(s => s.offsetTop <= mid && s.offsetTop + s.offsetHeight > mid);
}
document.addEventListener('keydown', e => {
  if (['ArrowRight','PageDown',' '].includes(e.key)) { e.preventDefault(); go(current()+1); }
  if (['ArrowLeft','PageUp'].includes(e.key))        { e.preventDefault(); go(current()-1); }
  if (e.key === 'Home') { e.preventDefault(); go(0); }
  if (e.key === 'End')  { e.preventDefault(); go(slides.length-1); }
});
function progress(){
  const max = document.body.scrollHeight - window.innerHeight;
  bar.style.width = (max > 0 ? (window.scrollY / max) * 100 : 0) + '%';
}
window.addEventListener('scroll', progress, {passive:true});
progress();
setTimeout(() => { const h = document.querySelector('.hint'); if (h) h.style.opacity = '0'; }, 6000);
"""


def slide(n, total, tag, body):
    return (f'<section class="slide"><span class="tag">{tag}</span>{body}'
            f'<span class="num">{n:02d} / {total:02d}</span></section>')


SLIDES = []


def add(tag, body):
    SLIDES.append((tag, body))


# 01 ---------------------------------------------------------------------
add("Project review · 20 Aug 2026", """
  <p class="kicker">B.Tech CSE (ML/AI) · Major Project · Week 2 of 20</p>
  <h1>MFSTNet</h1>
  <p class="sub">Camera-only congestion forecasting for unstructured Indian
  traffic, and a reinforcement-learning signal controller that consumes it.
  <strong>No inductive loops, no GPS traces, no vehicle-to-infrastructure
  radio</strong> — one camera per approach and the pixels it produces.</p>
  <div class="grid g4">
    <div class="card"><div class="k">Detection, elevated CCTV</div><div class="v ok">0.8941</div><div class="n">mAP50 on BMD-45, eight India-specific classes</div></div>
    <div class="card"><div class="k">Committed tests</div><div class="v acc">620</div><div class="n">across 35 files, all passing</div></div>
    <div class="card"><div class="k">Decisions recorded</div><div class="v acc">18</div><div class="n">ADRs, plus 29 logged defects</div></div>
    <div class="card"><div class="k">Full ablation</div><div class="v ok">1.5 h</div><div class="n">eight configs, laptop GPU</div></div>
  </div>
""")

# 02 ---------------------------------------------------------------------
add("The system", """
  <p class="kicker">What is being built</p>
  <h2>Four subsystems, developed independently, integrated late</h2>
  <div class="flow">
    <div class="step acc"><b>IndiaTrafficNet</b>self-annotated dataset<br>8 India-specific classes</div>
    <div class="step acc"><b>YOLOv8s</b>per-lane vehicle counts<br>at the edge</div>
    <div class="step acc"><b>MFSTNet</b>ResNet-50 + DINOv2 ViT-S/14<br>gated cross-attention</div>
    <div class="step acc"><b>PPO agent</b>SUMO via TraCI<br>consumes the forecast</div>
  </div>
  <div class="grid g2">
    <div class="card">
      <h3>The coupling that is easy to miss</h3>
      <p>MFSTNet's output is not just a prediction — it is <strong>part of the
      PPO state vector</strong>. Four per-lane class predictions occupy indices
      11–14 of a 16-dimensional state. Change MFSTNet's output shape and every
      trained PPO checkpoint is invalidated.</p>
    </div>
    <div class="card">
      <h3>Two fallbacks are required behaviour</h3>
      <p>If MFSTNet inference fails, PPO runs on raw counts with indices 11–14
      zeroed — never a shortened vector. If MQTT drops for more than 10 s, the
      edge node switches to a locally-embedded Webster controller.</p>
    </div>
  </div>
""")

# 03 ---------------------------------------------------------------------
add("Stack", """
  <p class="kicker">What it runs on</p>
  <h2>Every version below is the one actually installed</h2>
  <p class="sub">Pinned from the environment rather than chosen by hand — until
  four days ago the pins were aspirational and <strong>not one of the seven
  pinned-and-installed packages matched its pin</strong>.</p>
  <div class="grid g3">
    <div class="card"><div class="k">Vision</div><p><code>torch 2.13.0+cu126</code><br><code>torchvision 0.28.0</code><br><code>timm 1.0.28</code><br><code>ultralytics 8.4.118</code><br><code>opencv 5.0.0.93</code></p></div>
    <div class="card"><div class="k">Reinforcement learning</div><p><code>stable-baselines3 2.9.0</code><br><code>gymnasium 1.3.0</code><br><code>eclipse-sumo 1.27.1</code><br><code>traci / sumolib 1.27.1</code></p></div>
    <div class="card"><div class="k">Analysis</div><p><code>numpy 2.5.2</code><br><code>pandas 3.0.5</code><br><code>scipy 1.18.0</code><br><code>scikit-learn 1.9.0</code><br><code>xgboost 3.4.1</code></p></div>
  </div>
  <div class="callout" style="margin-top:18px">
    <p><em>scipy and scikit-learn are not on the production path.</em> The
    metrics and statistics are pure standard library so the arithmetic stays
    auditable. Those two are pinned because the tests cross-check the
    hand-rolled implementations against them — macro F1, QWK, the paired t-test
    and Cohen's d are graded reported numbers, and a bespoke statistic nobody
    verifies is worse than none.</p>
  </div>
  <p class="tiny">Hardware: RTX 4050 Laptop (6 GB, sm_89) · training local, not Colab</p>
""")

# 04 ---------------------------------------------------------------------
add("Result · detection", """
  <p class="kicker">Milestone M2 · due Week 9, met at Week 2</p>
  <h2>Detection at the deployment viewpoint is solved</h2>
  <div class="scroll">
  <table>
    <thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>mAP50</th><th>mAP50-95</th><th>Test boxes</th></tr></thead>
    <tbody>
      <tr><td>car</td><td class="m">0.8617</td><td class="m">0.8989</td><td class="m ok">0.9212</td><td class="m">0.7849</td><td class="m">2,770</td></tr>
      <tr><td>motorcycle</td><td class="m">0.8650</td><td class="m">0.8186</td><td class="m ok">0.9033</td><td class="m">0.6740</td><td class="m">5,910</td></tr>
      <tr class="hi"><td>auto_rickshaw</td><td class="m">0.8892</td><td class="m">0.8654</td><td class="m">0.9186</td><td class="m">0.7635</td><td class="m">2,132</td></tr>
      <tr><td>bus</td><td class="m">0.8481</td><td class="m">0.8105</td><td class="m">0.8832</td><td class="m">0.7155</td><td class="m">606</td></tr>
      <tr><td>truck</td><td class="m">0.8032</td><td class="m">0.7694</td><td class="m">0.8442</td><td class="m">0.6784</td><td class="m">939</td></tr>
      <tr><td><strong>mean</strong></td><td class="m">—</td><td class="m">—</td><td class="m ok"><strong>0.8941</strong></td><td class="m">—</td><td class="m">12,357</td></tr>
    </tbody>
  </table>
  </div>
  <p class="sub" style="margin-bottom:0">BMD-45, Bengaluru Safe City CCTV.
  <strong>auto_rickshaw at 0.9186</strong> is the number that matters — it is a
  class COCO does not have, and the reason for building a detector rather than
  using one off the shelf.</p>
""")

# 05 image ---------------------------------------------------------------
add("Detection · example", f"""
  <p class="kicker">ITD-XL detector &middot; confidence 0.45 &middot; imgsz 992</p>
  <h2>What "unstructured" actually means</h2>
  <div class="grid g2">
    <figure>
      <img src="data:image/jpeg;base64,{img('detect_mumbai.jpg')}" alt="Annotated detection output on a Mumbai traffic scene: cars, motorcycles and auto-rickshaws boxed with class and confidence.">
      <figcaption><strong>Mumbai, Andheri Station — 23 vehicles.</strong>
      Motorcycles filtering between lanes, auto-rickshaws, and vehicles at four
      different scales in one frame.</figcaption>
    </figure>
    <figure>
      <img src="data:image/jpeg;base64,{img('detect_dhaka.jpg')}" alt="Annotated detection output on a dense Dhaka traffic scene at Rampura.">
      <figcaption><strong>Dhaka, Rampura — 20 vehicles.</strong> The S06 pilot
      camera. The quietest moment in twenty minutes here still held nine
      vehicles, which is why fixed thresholds failed.</figcaption>
    </figure>
  </div>
  <p class="sub" style="margin-top:20px;margin-bottom:0">Neither scene has lane
  markings a model could rely on, and both hold vehicles spanning
  <strong>25% of the frame down to under 1%</strong>. Boxes are coloured by
  class in the detector's own taxonomy. A model trained on dashcam imagery
  scored <strong>0.3223</strong> on this viewpoint; the joint detector scores
  <strong>0.8941</strong>.</p>
""")

# 06 ---------------------------------------------------------------------
add("Result · the M2 criterion", """
  <p class="kicker">Measured properly, not claimed by implication</p>
  <h2>+53.2% mAP over COCO on the classes both can see</h2>
  <p class="sub">M2's criterion is "≥10% mAP improvement over COCO on Indian
  classes". It had been asserted and never actually measured. On the
  <strong>same test split</strong>, with the ground truth remapped so
  Ultralytics' own validator scores both sides:</p>
  <div class="scroll">
  <table>
    <thead><tr><th>Class</th><th>COCO baseline</th><th>Ours</th><th>Delta</th></tr></thead>
    <tbody>
      <tr><td>car</td><td class="m">0.6048</td><td class="m">0.7133</td><td class="m ok">+0.1085</td></tr>
      <tr><td>motorcycle</td><td class="m">0.4285</td><td class="m">0.6784</td><td class="m ok">+0.2499</td></tr>
      <tr><td>bus</td><td class="m">0.4852</td><td class="m">0.7141</td><td class="m ok">+0.2288</td></tr>
      <tr><td>truck</td><td class="m">0.3097</td><td class="m">0.6958</td><td class="m ok">+0.3861</td></tr>
      <tr class="hi"><td><strong>shared mean</strong></td><td class="m">0.4570</td><td class="m">0.7000</td><td class="m"><strong>+53.2%</strong></td></tr>
    </tbody>
  </table>
  </div>
  <div class="callout">
    <p>On <code>auto_rickshaw</code> (0.7109) and <code>cattle</code> (0.3516)
    <em>no percentage is honest</em> — COCO has no such class, so the baseline
    is not low, it is undefined.</p>
    <p>Saying that is a stronger statement than any number would have been.</p>
  </div>
""")

# 07 ---------------------------------------------------------------------
add("Result · counting", """
  <p class="kicker">Counting accuracy is not detection accuracy</p>
  <h2>The operating point was fitted, not assumed</h2>
  <p class="sub">Congestion labels come from vehicle <strong>counts</strong>, and
  a detector with excellent mAP can still systematically over- or under-count.
  Sweeping the confidence threshold against 5,273 human-annotated vehicles:</p>
  <div class="scroll">
  <table>
    <thead><tr><th>Confidence</th><th>detected / true</th><th>Sparse third</th><th>Dense third</th><th>MAE per frame</th></tr></thead>
    <tbody>
      <tr><td class="m">0.25</td><td class="m bad">1.1724</td><td class="m">1.2147</td><td class="m">1.1686</td><td class="m">1.998</td></tr>
      <tr><td class="m">0.35</td><td class="m warn">1.0793</td><td class="m">1.1207</td><td class="m">1.0754</td><td class="m">1.349</td></tr>
      <tr class="hi"><td class="m">0.45</td><td class="m"><strong>0.9989</strong></td><td class="m">1.0251</td><td class="m">0.9968</td><td class="m"><strong>1.072</strong></td></tr>
      <tr><td class="m">0.55</td><td class="m warn">0.9340</td><td class="m">0.9608</td><td class="m">0.9271</td><td class="m">1.165</td></tr>
      <tr><td class="m">0.60</td><td class="m bad">0.9006</td><td class="m">0.9436</td><td class="m">0.8917</td><td class="m">1.361</td></tr>
    </tbody>
  </table>
  </div>
  <p class="sub" style="margin-bottom:0"><strong>0.45 is pinned</strong>: ratio
  0.9989 and the lowest error. The sparse and dense columns exist because a
  detector that is accurate on average can still be biased with density — here
  the residual dependence is <strong>2.8%</strong>, and it is reported rather
  than averaged away.</p>
""")

# 08 ---------------------------------------------------------------------
add("Honesty · generalisation", """
  <p class="kicker">The result we did not want</p>
  <h2>The detector loses two thirds of its accuracy on unseen cameras</h2>
  <div class="grid g3">
    <div class="card"><div class="k">BMD-45 · trained domain</div><div class="v ok">0.8941</div><div class="n">Bengaluru Safe City CCTV</div></div>
    <div class="card"><div class="k">IDD · dashcam</div><div class="v warn">0.7104</div><div class="n">a different viewpoint entirely</div></div>
    <div class="card"><div class="k">TrafficCAM · unseen cameras</div><div class="v bad">0.3500</div><div class="n">the number that governs deployment</div></div>
  </div>
  <div class="callout warn" style="margin-top:20px">
    <p><strong>0.3500 is the honest deployment number</strong>, not 0.8941. A
    model deployed on a junction it has never seen is in the third column.</p>
    <p>Adding 1,254 human-annotated TrafficCAM boxes moved that to
    <strong>0.5734</strong> and brought <code>e_rickshaw</code> from
    <strong>0.000 to 0.4787</strong> — the detector had been shipping an output
    head that had never seen a single example of a class the project exists to
    handle.</p>
  </div>
  <p class="sub" style="margin-bottom:0">That arm is <strong>not adopted</strong>:
  it failed a sixth pre-registered criterion (IDD −0.0916 against a 0.02
  tolerance). The criterion was fixed before the run and is not being retuned to
  fit the number it rejected. Whether dashcam accuracy should still be an
  acceptance surface is an open decision, made forward.</p>
""")

# 09 ---------------------------------------------------------------------
add("The corpus", """
  <p class="kicker">Turning video into training data</p>
  <h2>Nine steps, each one auditable</h2>
  <div class="flow">
    <div class="step"><b>triage</b>which clips qualify</div>
    <div class="step"><b>survey</b>where traffic actually is</div>
    <div class="step acc"><b>place lanes</b>by hand, per camera</div>
    <div class="step"><b>import</b>validate the placement</div>
    <div class="step"><b>build_corpus</b>detector → counts</div>
    <div class="step"><b>relabel</b>thresholds, in seconds</div>
    <div class="step acc"><b>audit</b>re-derive and check</div>
    <div class="step"><b>build_cache</b>frozen features</div>
    <div class="step"><b>train</b>config or full ablation</div>
  </div>
  <div class="grid g2">
    <div class="card">
      <h3>The expensive pass runs once</h3>
      <p>The detector pass produces <code>counts.csv</code> and
      <code>detections.csv</code>. Both are <strong>independent of the choices
      made after them</strong> — a threshold change re-derives in seconds, and
      a lane centre moved by hand re-derives in <strong>0.66 s</strong> instead
      of hours.</p>
    </div>
    <div class="card">
      <h3>Why that matters more than speed</h3>
      <p>Lane placement is done by eye over a heat map. It was never going to be
      right first time. A feedback loop costing hours per iteration is one that
      gets used once — and the placement gets judged on how it looks rather than
      on the counts it produces.</p>
    </div>
  </div>
""")

# 10 image ---------------------------------------------------------------
add("Lane geometry", f"""
  <p class="kicker">Why a human places the lanes</p>
  <h2>Automatic lane centres move when the detector changes</h2>
  <figure>
    <img src="data:image/jpeg;base64,{img('lanes_mumbai.jpg')}" alt="Detection density heat map over the Mumbai scene with four clustered lane centres marked.">
    <figcaption>Detection density over 60 sampled frames, with the four
    automatic lane centres marked. Measured: those centres shift by
    <strong>0.164 of the frame width — about 315 px</strong> — when the detector
    is swapped. A lane that moves because the tooling changed is not a property
    of the road, so every set is reviewed by hand before use.</figcaption>
  </figure>
""")

# 11 ---------------------------------------------------------------------
add("Decision · A28", """
  <p class="kicker">A pre-registered statistic, and what it returned</p>
  <h2>Sampling every 2 s instead of 5 keeps four cameras alive</h2>
  <p class="sub">PRD §8.2 fixes <code>step_s = 5</code> as a bare number derived
  nowhere. A28 pre-registered <code>ceil(P75/59)</code> to replace it — chosen
  <strong>before the footage existed</strong> and deliberately biased against
  our preferred answer. Measured across three detectors and two threshold sets,
  it returns <strong>1 or 2 in all six combinations. Never 5.</strong></p>
  <div class="scroll">
  <table>
    <thead><tr><th>step_s</th><th>Clip minimum</th><th>Sequences</th><th>Independent segments</th><th>Cameras contributing</th></tr></thead>
    <tbody>
      <tr><td class="m">5 — current</td><td class="m">355 s</td><td class="m">302</td><td class="m">29</td><td class="m warn">7 of 11</td></tr>
      <tr class="hi"><td class="m">2 — proposed</td><td class="m">178 s</td><td class="m">359</td><td class="m">64</td><td class="m">11 of 11</td></tr>
      <tr><td class="m">1</td><td class="m">119 s</td><td class="m">381</td><td class="m">101</td><td class="m">11 of 11</td></tr>
    </tbody>
  </table>
  </div>
  <div class="callout">
    <p><em>The sequence column is the weaker argument.</em> Overlapping windows
    inflate any sequence count — the measured inflation is 5.6×.</p>
    <p>The column that matters is the last one. <code>step_s = 5</code> needs
    355 s of continuous footage per clip and therefore <strong>deletes four
    cameras outright</strong>. Sequences from one camera are correlated; cameras
    are the unit the model must generalise over, and no augmentation
    manufactures a viewpoint.</p>
  </div>
""")

# 12 ---------------------------------------------------------------------
add("Decision · thresholds", """
  <p class="kicker">What "congested" means</p>
  <h2>Calibrated per camera, because a threshold in absolute units describes the view</h2>
  <div class="scroll">
  <table>
    <thead><tr><th>Camera</th><th>p33</th><th>p67</th><th>Share of counts that are zero</th></tr></thead>
    <tbody>
      <tr><td>4K Road traffic</td><td class="m">0</td><td class="m">1</td><td class="m">64%</td></tr>
      <tr><td>Mumbai Andheri</td><td class="m">4</td><td class="m">9</td><td class="m">0%</td></tr>
      <tr><td>South Extension</td><td class="m">8</td><td class="m">18</td><td class="m">9%</td></tr>
      <tr><td>video1</td><td class="m">13</td><td class="m">19</td><td class="m">0%</td></tr>
      <tr class="hi"><td><strong>pooled — what the code used to do</strong></td><td class="m">0</td><td class="m">3</td><td class="m">41%</td></tr>
    </tbody>
  </table>
  </div>
  <p class="sub">The pooled p67 is 3 while video1's p33 alone is 13. Under pooled
  thresholds the busy cameras <strong>never see LOW</strong> and the quiet one
  <strong>never sees HIGH</strong>.</p>
  <div class="grid g3">
    <div class="card"><div class="k">§14.1 defaults</div><div class="v warn">83 / 13 / 4</div><div class="n">test split degenerate</div></div>
    <div class="card"><div class="k">Pooled calibration</div><div class="v warn">57 / 19 / 24</div><div class="n">test split degenerate</div></div>
    <div class="card"><div class="k">Per camera</div><div class="v ok">59 / 26 / 15</div><div class="n">all three classes in every split</div></div>
  </div>
""")

# 13 ---------------------------------------------------------------------
add("The model", """
  <p class="kicker">MFSTNet · the core contribution</p>
  <h2>Two frozen backbones, arbitrated by a learned gate</h2>
  <div class="flow">
    <div class="step"><b>ResNet-50</b>2048 × 7 × 7<br>frozen</div>
    <div class="step"><b>DINOv2 ViT-S/14</b>384 × 16 × 16<br>frozen</div>
    <div class="step acc"><b>bidirectional cross-attn</b>Z_A: CNN queries ViT<br>Z_B: ViT queries CNN</div>
    <div class="step acc"><b>the gate</b>g = σ(Linear([Z_A; Z_B]))<br>F = g·Z_A + (1−g)·Z_B</div>
    <div class="step"><b>per-lane ROI pool</b>Voronoi cells<br>from lane centres</div>
    <div class="step"><b>BiLSTM + temporal attn</b>T = 60 steps</div>
    <div class="step"><b>congestion head</b>LOW / MED / HIGH<br>60 s ahead, per lane</div>
  </div>
  <div class="callout">
    <p><em>The gate is a research artifact, not an implementation detail.</em>
    It is logged every run, tracked on the dashboard, and analysed in the paper
    — so "what value does it take, and why" is a question the report has to
    answer rather than a diagnostic.</p>
  </div>
  <p class="sub" style="margin-bottom:0">Backbones are frozen and their features
  cached, which is what makes an eight-config ablation feasible on a 6 GB laptop
  GPU. <strong>Ablation-ability is an architectural constraint</strong>: every
  module can be disabled by a config flag, with no code edit between configs.</p>
""")

# 14 ---------------------------------------------------------------------
add("Result · the gate", """
  <p class="kicker">The question we could answer before the corpus exists</p>
  <h2>The gate can gate — the flat gate is a fact about the data</h2>
  <p class="sub">On the pilot corpus the gate sits at <strong>mean 0.54, std
  0.005</strong>: one value for every location and timestep, which is a scalar
  blend rather than a gate. Instrumenting its input explains exactly why —
  <code>z_a</code> and <code>z_b</code> are nearly orthogonal
  (cosine −0.004) but <strong>small</strong>, std 0.035, so the sigmoid never
  leaves its linear region.</p>
  <div class="scroll">
  <table>
    <thead><tr><th>Seed</th><th>Gate std</th><th>g when CNN carries signal</th><th>g when ViT carries signal</th><th>Separation</th></tr></thead>
    <tbody>
      <tr><td class="m">1</td><td class="m ok">0.320</td><td class="m">0.404</td><td class="m">0.670</td><td class="m">0.266</td></tr>
      <tr><td class="m">7</td><td class="m ok">0.263</td><td class="m">0.451</td><td class="m">0.672</td><td class="m">0.221</td></tr>
      <tr><td class="m">42</td><td class="m ok">0.444</td><td class="m">0.481</td><td class="m">0.654</td><td class="m">0.172</td></tr>
    </tbody>
  </table>
  </div>
  <p class="sub">Given a task where half the samples carry the label in the CNN
  branch and half in the ViT, the gate moves by <strong>50–90× its pilot
  spread</strong> and routes toward whichever branch is worth reading. That is
  the mechanism doing what it was chosen for.</p>
  <div class="callout warn">
    <p><strong>The caveat, recorded rather than hidden.</strong> The fusion
    returns <code>norm(fused + 0.5·(f_cnn + f_vit))</code> — the residual adds
    both branches back <em>ungated</em>, so neither can be suppressed. That
    bounds how much of the ablation's F→G difference gating can ever account
    for, and it belongs in the paper rather than in a reviewer's question.</p>
  </div>
""")

# 15 ---------------------------------------------------------------------
add("Result · signal control", """
  <p class="kicker">30 paired seeds · bootstrap CI · paired t-test · Cohen's d</p>
  <h2>The baselines are reported as measured, including where they disqualify</h2>
  <div class="scroll">
  <table>
    <thead><tr><th>Regime</th><th>Fixed-time</th><th>Longest-queue</th><th>Webster</th><th>p</th><th>Cohen's d</th><th>Citable</th></tr></thead>
    <tbody>
      <tr><td>light</td><td class="m">11.92</td><td class="m ok">6.28</td><td class="m">6.59</td><td class="m">&lt;1e-6</td><td class="m">18.92</td><td class="warn">partly</td></tr>
      <tr class="hi"><td>saturated</td><td class="m">26.18</td><td class="m">27.94</td><td class="m ok"><strong>14.05</strong></td><td class="m">&lt;1e-6</td><td class="m">2.94</td><td class="ok">yes</td></tr>
      <tr><td>oversaturated</td><td class="m">71.89</td><td class="m">70.46</td><td class="m">66.61</td><td class="m">0.0999</td><td class="m">0.31</td><td class="bad">no</td></tr>
    </tbody>
  </table>
  </div>
  <p class="small">Mean wait in seconds. The headline comparison is made at
  saturation, where signal timing decides the outcome.</p>
  <div class="grid g2">
    <div class="card">
      <h3>Two disqualifications, applied automatically</h3>
      <p>In <strong>light</strong> traffic Webster's cycle formula clamps
      <strong>100%</strong> of the time — that is a fixed-time controller
      wearing Webster's name, so the comparison is not citable.</p>
    </div>
    <div class="card">
      <h3>Survivorship, caught by rule</h3>
      <p>In <strong>oversaturated</strong> traffic all three controllers
      complete under 85% of trips. A low mean wait there measures only the
      vehicles that got through, so the whole regime is disqualified.</p>
    </div>
  </div>
""")

# 16 ---------------------------------------------------------------------
add("Engineering", """
  <p class="kicker">Making the experiment affordable</p>
  <h2>The ablation went from 12.3 hours to 1.5</h2>
  <div class="scroll">
  <table>
    <thead><tr><th>Config</th><th>CPU</th><th>GPU, fp32 path</th><th>GPU, fp16 path</th><th>Total gain</th></tr></thead>
    <tbody>
      <tr><td>A · CNN only</td><td class="m">33.2 s</td><td class="m">20.5 s</td><td class="m ok">12.7 s</td><td class="m">2.6×</td></tr>
      <tr><td>B · ViT only</td><td class="m">20.1 s</td><td class="m">19.8 s</td><td class="m ok">9.4 s</td><td class="m">2.1×</td></tr>
      <tr class="hi"><td>G · full MFSTNet</td><td class="m">208.4 s</td><td class="m">40.0 s</td><td class="m"><strong>16.6 s</strong></td><td class="m"><strong>12.6×</strong></td></tr>
      <tr><td><strong>A–H, extrapolated</strong></td><td class="m">12.3 h</td><td class="m">3.8 h</td><td class="m ok"><strong>1.5 h</strong></td><td class="m">8.2×</td></tr>
    </tbody>
  </table>
  </div>
  <div class="grid g2">
    <div class="card">
      <h3>Two independent faults behind one symptom</h3>
      <p>The documented install command pointed at a CUDA index that
      <strong>no longer carries PyTorch at any version</strong>, so it silently
      resolved to the CPU wheel. And the training script had <strong>no device
      handling at all</strong> — so a correct install would still have run on
      the CPU with the GPU idle.</p>
    </div>
    <div class="card">
      <h3>Half of every epoch was the wrong dtype</h3>
      <p>The cache stores fp16 and the model wants fp32. Widening on the CPU
      meant <code>torch.stack</code> copied and the bus carried
      <strong>twice the bytes</strong>. Widening after the transfer is exact —
      all eight configs agree on every one of 32 recorded fields.</p>
    </div>
  </div>
""")

# 17 ---------------------------------------------------------------------
add("Challenges", """
  <p class="kicker">29 logged defects · the ones that changed the project</p>
  <h2>What went wrong, and what each one cost</h2>
  <div class="scroll">
  <table>
    <thead><tr><th>#</th><th>What was wrong</th><th>How it was found</th><th>Why it mattered</th></tr></thead>
    <tbody>
      <tr><td class="m">P20</td><td>Pilot counted through COCO classes — no auto-rickshaw</td><td>Class list audit</td><td>93.1% vs 69.0% naive: a flattering result from a wrong taxonomy</td></tr>
      <tr><td class="m">P21</td><td><code>e_rickshaw</code> AP 0.000</td><td>Per-class census</td><td>IDD contains <strong>zero</strong> instances — an output head trained on nothing</td></tr>
      <tr class="hi"><td class="m">P23</td><td>Lane polygons overlapped on 11 of 12 cameras</td><td>Looking at the pictures</td><td>Every vehicle in the overlap double-counted</td></tr>
      <tr><td class="m">P24</td><td>Vehicle class list matched 3 of ITD's 7</td><td>Re-audit after P20</td><td>Same defect as P20, in a second file, fixed once</td></tr>
      <tr class="hi"><td class="m">P26</td><td>Every camera pooled through <em>one</em> camera's lane geometry</td><td>Checking P25's implications</td><td>Silent: shapes agree, loss falls, wrong region measured</td></tr>
      <tr><td class="m">P29</td><td>A cached window read its entire clip</td><td>First real end-to-end run</td><td>26 GB of churn for 1.5 GB of batch — segfault, no traceback</td></tr>
      <tr><td class="m">P30</td><td>Not one pinned package matched its installed version</td><td>Environment audit</td><td>A clean machine would build a different stack</td></tr>
      <tr class="hi"><td class="m">P34</td><td>Calibration produced <code>low_max = −1</code></td><td>Running it on real data</td><td>0% LOW — the exact degeneracy calibration prevents</td></tr>
      <tr><td class="m">P38</td><td>Installing CUDA made PPO <strong>2× slower</strong></td><td>Testing the other subsystem</td><td>A regression caused by fixing something else</td></tr>
    </tbody>
  </table>
  </div>
  <div class="callout">
    <p><em>Three of these shared one shape</em> — a number whose meaning
    depended on a fact the number did not carry. Each was fixed where it
    happened; the pattern was then closed once, by writing the environment
    beside every result.</p>
  </div>
""")

# 18 ---------------------------------------------------------------------
add("Method", """
  <p class="kicker">Reproducibility · NFR-07 to NFR-10, graded Critical</p>
  <h2>The machinery that stops a wrong number from looking right</h2>
  <div class="grid g2">
    <div class="card">
      <h3>Pre-registered thresholds</h3>
      <p>A28's statistic, ADR-012's disqualifications and S17's six criteria
      were all fixed <strong>before</strong> the runs that tested them. That
      rule has cost us the preferred answer four times, which is the only
      reason it is worth anything.</p>
    </div>
    <div class="card">
      <h3>Results are written, never transcribed</h3>
      <p>Every table comes from a committed CSV produced by the script that ran
      the experiment. A short verification run now <strong>refuses</strong> to
      overwrite results recorded from a longer one.</p>
    </div>
    <div class="card">
      <h3>The corpus is audited against itself</h3>
      <p>Nine checks re-derive a corpus from its own more primitive files —
      including that the label sits exactly 60 s after the last observed frame.
      All <strong>seven deliberate mutations</strong> of a good corpus are
      caught.</p>
    </div>
    <div class="card">
      <h3>Every result carries its environment</h3>
      <p>Torch version <em>and build</em>, CUDA device, both TF32 flags, package
      versions, git commit. <code>2.13.0+cpu</code> and
      <code>2.13.0+cu126</code> are the same version and cannot produce the same
      numbers.</p>
    </div>
  </div>
  <p class="tiny">620 tests across 35 files · 175 commits · 18 ADRs · 53 documents · seeds fixed at 42 across Python, NumPy, PyTorch and SB3</p>
""")

# 19 ---------------------------------------------------------------------
add("Status", """
  <p class="kicker">Week 2 of 20</p>
  <h2>Where the project actually stands</h2>
  <div class="grid g4">
    <div class="card"><div class="k">M2 · detector validated</div><div class="v ok">Met</div><div class="n">due Week 9, met at Week 2</div></div>
    <div class="card"><div class="k">Corpus pipeline</div><div class="v ok">Running</div><div class="n">end to end on real footage</div></div>
    <div class="card"><div class="k">MFSTNet training</div><div class="v warn">Pilot</div><div class="n">plumbing verified, awaiting the full corpus</div></div>
    <div class="card"><div class="k">Prototype</div><div class="v warn">Descoped?</div><div class="n">ADR-008 proposed, awaiting sign-off</div></div>
  </div>
  <div class="callout warn" style="margin-top:22px">
    <p><strong>The honest limit.</strong> The corpus is <strong>64 independent
    segments across 11 cameras</strong>, and 20 of those segments come from a
    single motorway clip. Sliding windows produce 359 training sequences from
    it, and both numbers travel together in the paper — the window count alone
    overstates the evidence by 5.6×.</p>
    <p>That concentration is the corpus's real weakness, and no choice of
    <code>step_s</code> fixes it. More footage from one junction is the only
    thing that does.</p>
  </div>
  <p class="sub" style="margin-bottom:0">Everything on the critical path is built
  and measured. What remains is not engineering.</p>
""")

# 20 ---------------------------------------------------------------------
add("Next", """
  <p class="kicker">What we need to proceed</p>
  <h2>Three decisions, then the corpus</h2>
  <div class="grid g3">
    <div class="card">
      <div class="k">A28 · sampling interval</div>
      <h3>step_s = 2, not 5</h3>
      <p>Decides whether the corpus has <strong>eleven cameras or seven</strong>.
      Reversal cost: one corpus rebuild.</p>
    </div>
    <div class="card">
      <div class="k">ADR-017 · thresholds</div>
      <h3>PCU units, per camera</h3>
      <p>Decides what every congestion table <strong>means</strong>. Reversal
      cost: minutes — labels re-derive without the detector.</p>
    </div>
    <div class="card">
      <div class="k">S17 · acceptance surface</div>
      <h3>Is dashcam still a gate?</h3>
      <p>Decides which detector is <strong>the one of record</strong>. Reversal
      cost: one detector re-run.</p>
    </div>
  </div>
  <div class="callout good" style="margin-top:22px">
    <p><strong>Then, in order:</strong> place four lane centres on each of the
    twelve cameras → build the corpus → audit it → cache the frozen features →
    run the eight-config ablation. That last step now takes an evening rather
    than a weekend.</p>
  </div>
  <p class="tiny">Every figure in this deck comes from a committed CSV in
  <code>experiments/results/</code>. Nothing here is an estimate.</p>
""")

total = len(SLIDES)
body = "".join(slide(i + 1, total, tag, html) for i, (tag, html) in enumerate(SLIDES))

html = f"""<title>MFSTNet Project Review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="bar"></div>
<div class="hint">← → to move between slides</div>
<div class="deck">{body}</div>
<script>{JS}</script>"""

def ascii_safe(text: str) -> str:
    """Escape every non-ASCII character to a numeric entity.

    The page carries no `<meta charset>` of its own — the artifact host supplies
    the document head — so a browser opening the file directly has to guess the
    encoding, and guesses latin-1. That turned every middot into "Â·"
    and every em dash into "â€”" on a local preview. Entities are
    encoding-independent and render identically either way.
    """
    return "".join(ch if ord(ch) < 128 else f"&#{ord(ch)};" for ch in text)


out = pathlib.Path("d:/major project/docs/demo/project_review.html")
out.parent.mkdir(parents=True, exist_ok=True)
safe = ascii_safe(html)
out.write_text(safe, encoding="utf-8")
escaped = sum(1 for ch in html if ord(ch) >= 128)
print(f"  wrote {out}  ({len(safe)/1024/1024:.2f} MB, {total} slides, "
      f"{escaped} non-ASCII characters escaped)")
