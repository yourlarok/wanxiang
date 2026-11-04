DESIGN_CSS = """
body{padding:clamp(16px,3vw,34px);line-height:1.55;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}
.wx-artboard{position:relative;isolation:isolate;width:100%;max-width:1180px;margin:0 auto;overflow:hidden}
.wx-composition{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:clamp(12px,2vw,24px);align-items:start}
.wx-header{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,8fr) minmax(120px,4fr);gap:24px;align-items:end;margin-bottom:clamp(18px,3vw,34px)}
.wx-heading{grid-column:1/-1;max-width:760px}
.wx-kicker{display:flex;align-items:center;gap:8px;margin:0 0 10px;color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase}
.wx-kicker:before{content:"";width:22px;height:2px;background:currentColor}
.wx-title{margin:0;max-width:18ch;font-size:clamp(26px,4.5vw,52px);font-weight:720;line-height:1.06;letter-spacing:-.035em;text-wrap:balance}
.wx-subtitle{max-width:58ch;margin:12px 0 0;color:var(--muted);font-size:clamp(12px,1.5vw,15px);line-height:1.65}
.wx-main{grid-column:span 8;min-width:0}.wx-aside{grid-column:span 4;min-width:0}.wx-full{grid-column:1/-1;min-width:0}
.wx-stage{position:relative;min-width:0;border-radius:calc(var(--radius) + 6px)}
.wx-stage>svg,.wx-stage>canvas{display:block;width:100%;height:auto}
.wx-note{padding:4px 0 4px 16px;border-left:2px solid var(--accent)}
.wx-note strong{display:block;margin-bottom:4px;font-size:13px}.wx-note p{margin:0;color:var(--muted);font-size:12px}
.wx-number{font-size:clamp(32px,6vw,72px);font-weight:750;line-height:1;letter-spacing:-.055em;font-variant-numeric:tabular-nums}
.wx-label{color:var(--muted);font-size:10px;font-weight:650;letter-spacing:.12em;text-transform:uppercase}
.wx-caption{margin-top:10px;color:var(--muted);font-size:11px;line-height:1.55}
.wx-rule{height:1px;margin:18px 0;background:color-mix(in srgb,var(--muted) 28%,transparent)}
.wx-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:16px}
.wx-toolbar button{border:1px solid color-mix(in srgb,var(--accent) 48%,transparent);border-radius:999px;background:color-mix(in srgb,var(--accent) 12%,var(--surface));color:var(--ink);padding:8px 14px;font-size:12px;transition:transform 160ms cubic-bezier(.2,.8,.2,1),background 160ms}
.wx-toolbar button:hover{background:color-mix(in srgb,var(--accent) 22%,var(--surface));transform:translateY(-1px)}
.wx-toolbar button:active{transform:translateY(0) scale(.97)}
.wx-toolbar button[aria-pressed=true]{background:var(--accent);color:var(--bg)}
.wx-control{display:grid;grid-template-columns:auto minmax(100px,1fr) auto;align-items:center;gap:12px;width:100%;color:var(--muted);font-size:11px}
.wx-control input{width:100%;accent-color:var(--accent);cursor:pointer}
.wx-control output{min-width:3ch;color:var(--ink);font-variant-numeric:tabular-nums;text-align:right}
.wx-annotation{position:absolute;max-width:180px;padding:8px 11px;border:1px solid color-mix(in srgb,var(--muted) 28%,transparent);border-radius:10px;background:color-mix(in srgb,var(--surface) 84%,transparent);box-shadow:0 8px 24px #00000014;font-size:11px;backdrop-filter:blur(12px)}
.wx-scene{font-family:var(--font);overflow:visible}
.wx-scene text{paint-order:stroke;stroke:transparent;stroke-width:0}
.wx-scene [data-motion]{transform-box:fill-box;transform-origin:center}
[data-motion=enter]{animation:wx-enter 520ms cubic-bezier(.16,1,.3,1) both;animation-delay:var(--delay,0ms)}
[data-motion=rise]{animation:wx-rise 620ms cubic-bezier(.16,1,.3,1) both;animation-delay:var(--delay,0ms)}
[data-motion=draw]{stroke-dasharray:1200;stroke-dashoffset:1200;animation:wx-draw 900ms cubic-bezier(.65,0,.35,1) forwards;animation-delay:var(--delay,0ms)}
[data-motion=pulse]{animation:wx-pulse 2.8s ease-in-out infinite;animation-delay:var(--delay,0ms)}
[data-motion=float]{animation:wx-float 5s ease-in-out infinite;animation-delay:var(--delay,0ms)}
@keyframes wx-enter{from{opacity:0;transform:translateY(12px) scale(.975)}to{opacity:1;transform:translateY(0) scale(1)}}
@keyframes wx-rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
@keyframes wx-draw{to{stroke-dashoffset:0}}
@keyframes wx-pulse{0%,100%{opacity:.65;transform:scale(1)}50%{opacity:1;transform:scale(1.06)}}
@keyframes wx-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@media(max-width:640px){.wx-header{grid-template-columns:1fr}.wx-main,.wx-aside{grid-column:1/-1}.wx-title{font-size:30px}.wx-composition{gap:16px}}
@media(max-height:700px){body{padding:18px}.wx-header{margin-bottom:16px}.wx-title{font-size:clamp(24px,4vw,36px)}.wx-subtitle{margin-top:8px}.wx-stage>svg,.wx-stage>canvas{height:min(46vh,360px);min-height:170px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
"""

MOTION_JS = """
document.querySelectorAll('[data-parallax]').forEach(root=>{
  root.addEventListener('pointermove',event=>{
    const bounds=root.getBoundingClientRect();
    root.style.setProperty('--pointer-x',((event.clientX-bounds.left)/bounds.width-.5).toFixed(3));
    root.style.setProperty('--pointer-y',((event.clientY-bounds.top)/bounds.height-.5).toFixed(3));
  });
  root.addEventListener('pointerleave',()=>{root.style.setProperty('--pointer-x',0);root.style.setProperty('--pointer-y',0)});
});
document.querySelectorAll('[data-replay]').forEach(button=>button.addEventListener('click',()=>{
  const root=button.closest('.wx-artboard')||document.body;
  root.querySelectorAll('[data-motion]').forEach(element=>{
    const motion=element.getAttribute('data-motion');
    element.removeAttribute('data-motion');
    void element.getBoundingClientRect();
    element.setAttribute('data-motion',motion);
  });
}));
"""
