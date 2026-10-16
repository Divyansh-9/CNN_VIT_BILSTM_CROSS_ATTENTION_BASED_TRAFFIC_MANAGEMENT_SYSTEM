"""P103 — a lane-placement page for the three transfer cameras.

    python scripts/p103_lane_page.py

Shows two frames of each camera's **calibration hour** (Sun 18:08; no test
hour is shown), at 25% and 75% of the hour. The reviewer clicks to add a lane
centre on each approach's queue, drags to adjust, and sees every pixel tinted
by the lane it would be counted in (nearest centre within 0.25, in normalised
coordinates, exactly as `mfstnet.corpus.lanes.assign_to_lane` measures).
Nothing is seeded by a detector, so no frame is counted before lanes exist.

Writes `data/_bellevue/p103/place_lanes_p103.html`: footage, so it is not
committed or published (the licence is unresolved). The page exports JSON in
the shape `scripts/import_lane_centres.py` reads, with the approach the
reviewer named for each centre.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

CAMERAS = {
    "150th_Eastgate": Path("D:/bellevue/150th_Eastgate/150th_Eastgate/"
                           "Bellevue_150th_Eastgate__2017-09-10_18-08-24.mp4"),
    "150th_Newport": Path("D:/bellevue/150th_Newport-20261015T133042Z-1-001/150th_Newport/"
                          "Bellevue_150th_Newport__2017-09-10_18-08-24.mp4"),
    "150th_SE38th": Path("D:/bellevue/NE8th-20261015T135807Z-1-001/150th_SE38th/"
                         "Bellevue_150th_SE38th__2017-09-10_18-08-24.mp4"),
}
OUT = Path("data/_bellevue/p103/place_lanes_p103.html")

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Place P103 lanes</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--ink:#e6edf3;--muted:#8b949e;--line:#30363d;--accent:#6366f1}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
main{max-width:1320px;margin:0 auto;padding:16px}h1{font-size:20px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 6px}
p,li{color:var(--muted);margin:3px 0}.cam{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;margin-top:14px}
.frames{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:900px){.frames{grid-template-columns:1fr}}
.wrap{position:relative;line-height:0;cursor:crosshair}.wrap img{width:100%;display:block;border-radius:6px}
.wrap canvas{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;border-radius:6px}
.c{position:absolute;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:#fff;border:3px solid #000;cursor:move;z-index:2}
.c span{position:absolute;left:18px;top:-4px;font:600 12px/1 system-ui;color:#fff;background:#000a;padding:2px 4px;border-radius:3px;white-space:nowrap}
.lanes{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}.lane{display:flex;align-items:center;gap:6px;background:#0d1117;border:1px solid var(--line);border-radius:6px;padding:4px 8px}
.lane b{width:12px;height:12px;border-radius:3px;display:inline-block}.lane input{width:150px;background:transparent;color:var(--ink);border:0;border-bottom:1px solid var(--line)}
button{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:6px 10px;font:600 13px system-ui;cursor:pointer}button.ghost{background:transparent;border:1px solid var(--line);color:var(--ink)}
textarea{width:100%;height:150px;background:#0d1117;color:var(--ink);border:1px solid var(--line);border-radius:6px;font:12px ui-monospace,monospace;margin-top:8px}
</style></head><body><main>
<h1>Place lanes: Eastgate, Newport, SE38th (P103)</h1>
<p>Frames come from each camera's <b>calibration hour</b> (Sun 18:08), at 25% and 75% of the hour. No test hour is shown and no detector has run.</p>
<ul>
<li><b>Click</b> on an approach's queue to add a centre (it appears on both frames). <b>Drag</b> a centre to move it. <b>Remove last</b> undoes.</li>
<li>Every pixel is tinted by the lane it would be counted in: the nearest centre, within 0.25 of the frame. Uncoloured ground is not counted.</li>
<li>Check: one centre per approach; no region swallowing the junction box; no approach missing; regions on <b>queues</b>, not on the crossing.</li>
<li>Name each centre's approach (e.g. "northbound queue"). Then <b>Copy JSON</b> and save it as <code>data/_bellevue/p103/lane_centres_p103.json</code>.</li>
</ul>
<div id="cams"></div>
<h2>Export</h2>
<input id="who" placeholder="Reviewer name (recorded verbatim)" style="width:320px;padding:6px;background:#0d1117;color:var(--ink);border:1px solid var(--line);border-radius:6px">
<button id="copy">Copy JSON</button>
<textarea id="out" readonly></textarea>
</main>
<script>
const CAMS=__CAMS__, R=0.25;
const COLORS=["#2878e6","#ff8c28","#c83cc8","#3cbe3c","#e6c828","#28c8c8"];
const state={};
function hex(c){return [1,3,5].map(i=>parseInt(c.slice(i,i+2),16))}
function draw(cam){
  const s=state[cam.camera];
  s.views.forEach(v=>{
    const im=v.img, cv=v.canvas; if(!im.naturalWidth)return;
    const W=160,H=90; cv.width=W; cv.height=H; const ctx=cv.getContext('2d'); const d=ctx.createImageData(W,H);
    for(let y=0;y<H;y++)for(let x=0;x<W;x++){
      const nx=(x+.5)/W, ny=(y+.5)/H; let best=-1, bd=1e9;
      s.pts.forEach((p,i)=>{const dd=Math.hypot(nx-p.c[0],ny-p.c[1]); if(dd<bd){bd=dd;best=i}});
      const k=(y*W+x)*4; if(best>=0&&bd<=R){const [r,g,b]=hex(COLORS[best%COLORS.length]); d.data[k]=r;d.data[k+1]=g;d.data[k+2]=b;d.data[k+3]=80}
    }
    ctx.putImageData(d,0,0);
    v.wrap.querySelectorAll('.c').forEach(e=>e.remove());
    s.pts.forEach((p,i)=>{
      const c=document.createElement('div');c.className='c';c.style.left=(p.c[0]*100)+'%';c.style.top=(p.c[1]*100)+'%';
      c.style.borderColor=COLORS[i%COLORS.length];c.innerHTML='<span>'+(i+1)+(p.name?' '+p.name:'')+'</span>';
      c.addEventListener('pointerdown',ev=>{ev.preventDefault();ev.stopPropagation();c.setPointerCapture(ev.pointerId);
        const move=e=>{const r=v.img.getBoundingClientRect();p.c=[Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))];draw(cam)};
        const up=()=>{c.removeEventListener('pointermove',move);c.removeEventListener('pointerup',up);export_()};
        c.addEventListener('pointermove',move);c.addEventListener('pointerup',up);});
      v.wrap.appendChild(c);
    });
  });
  const L=s.lanesEl; L.innerHTML='';
  s.pts.forEach((p,i)=>{const d=document.createElement('div');d.className='lane';
    d.innerHTML='<b style="background:'+COLORS[i%COLORS.length]+'"></b>'+(i+1)+' <input placeholder="approach name">';
    const inp=d.querySelector('input'); inp.value=p.name||''; inp.oninput=()=>{p.name=inp.value;export_();draw(cam)}; L.appendChild(d);});
  export_();
}
function export_(){
  const rows=CAMS.map(cam=>({clip:cam.clip,camera:cam.camera,reviewer:document.getElementById('who').value||'unrecorded',
    lanes:state[cam.camera].pts.map(p=>({centre:[+p.c[0].toFixed(4),+p.c[1].toFixed(4)],approach:p.name||''}))}));
  document.getElementById('out').value=JSON.stringify(rows,null,1);
}
CAMS.forEach(cam=>{
  const sec=document.createElement('div');sec.className='cam';
  sec.innerHTML='<h2>'+cam.camera+'</h2><p>'+cam.clip+'</p><div class="frames"></div><div class="lanes"></div>'+
    '<div style="margin-top:8px"><button class="ghost rm">Remove last</button> <button class="ghost clr">Clear</button></div>';
  document.getElementById('cams').appendChild(sec);
  const s=state[cam.camera]={pts:[],views:[],lanesEl:sec.querySelector('.lanes')};
  cam.frames.forEach(b64=>{
    const wrap=document.createElement('div');wrap.className='wrap';
    const img=document.createElement('img');img.src='data:image/jpeg;base64,'+b64;img.alt=cam.camera+' frame';
    const canvas=document.createElement('canvas');wrap.appendChild(img);wrap.appendChild(canvas);
    sec.querySelector('.frames').appendChild(wrap);
    wrap.addEventListener('click',e=>{const r=img.getBoundingClientRect();
      s.pts.push({c:[(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height],name:''});draw(cam)});
    img.onload=()=>draw(cam); s.views.push({img,canvas,wrap});
  });
  sec.querySelector('.rm').onclick=()=>{s.pts.pop();draw(cam)};
  sec.querySelector('.clr').onclick=()=>{s.pts=[];draw(cam)};
});
document.getElementById('who').oninput=export_;
document.getElementById('copy').onclick=()=>{const o=document.getElementById('out');o.select();try{navigator.clipboard.writeText(o.value)}catch(e){}};
window.addEventListener('resize',()=>CAMS.forEach(draw));
export_();
</script></body></html>"""


def frame_at(path: Path, fraction: float) -> str:
    import cv2

    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) * fraction))
    ok, image = capture.read()
    capture.release()
    if not ok:
        raise SystemExit(f"{path}: no frame at {fraction}")
    ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return base64.b64encode(jpeg.tobytes()).decode()


def main() -> int:
    cams = []
    for camera, path in CAMERAS.items():
        if not path.is_file():
            raise SystemExit(f"{camera}: {path} not found")
        cams.append({"camera": camera, "clip": path.name,
                     "frames": [frame_at(path, 0.25), frame_at(path, 0.75)]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(PAGE.replace("__CAMS__", json.dumps(cams)), encoding="utf-8")
    print(f"  wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB): "
          f"{', '.join(c['camera'] for c in cams)}, calibration hour only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
