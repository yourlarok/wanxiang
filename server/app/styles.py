DEFAULT_TOKENS = {
    "font": "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif",
    "plot_family": "sans-serif",
    "plot_fonts": "PingFang SC,Microsoft YaHei,Noto Sans CJK SC,Source Han Sans SC,SimHei,Arial Unicode MS",
    "radius": "12px",
    "border_width": "1px",
    "shadow": "none",
    "texture": "none",
}

STYLE_GUIDES = {
    "textbook": {
        "background": "#0e131c", "surface": "#171f2c", "ink": "#e7ecf4", "muted": "#8b98ab",
        "accent": "#a894ff", "highlight": "#f0a660",
        "guidance": "教材式解释：先给直观例子，再给定义；使用卡片、嵌套框、标注和短句，避免装饰性大段文字。",
    },
    "blueprint": {
        "background": "#0b1c2b", "surface": "#102a3e", "ink": "#d9edf5", "muted": "#83a8ba",
        "accent": "#63c7e6", "highlight": "#f2c879", "radius": "4px",
        "guidance": "蓝图式技术表达：细线、网格、精确标注、坐标和构造关系，减少无意义渐变。",
    },
    "minimal": {
        "background": "#f5f4ef", "surface": "#ffffff", "ink": "#20242a", "muted": "#68707a",
        "accent": "#4f62c9", "highlight": "#c96942",
        "guidance": "极简教学表达：大量留白、单一强调色、少而准的标注，优先内容层级而非卡片堆叠。",
    },
    "chalk": {
        "background": "#18302b", "surface": "#203b34", "ink": "#edf0dc", "muted": "#b0bba6",
        "accent": "#e7d88c", "highlight": "#e89b7b",
        "plot_family": "serif", "plot_fonts": "Kaiti SC,STKaiti,KaiTi,PingFang SC,Microsoft YaHei",
        "guidance": "黑板推导风格：手算步骤、圈注、箭头与分项解释，适合公式和概念直觉。",
    },
    "anime": {
        "background": "#edf6ff", "surface": "#fffdfd", "ink": "#293454", "muted": "#74809d",
        "accent": "#f26393", "highlight": "#38b6d9", "radius": "20px", "border_width": "2px",
        "shadow": "5px 5px 0 #8ba6cf40", "texture": "radial-gradient(circle at 15% 10%,#ffd9e780,transparent 32%),radial-gradient(circle at 85% 0,#c8f3ff99,transparent 38%)",
        "guidance": "动漫赛璐璐风：明亮粉蓝配色、清晰深色描边、圆润形体、轻量高光和活泼但克制的视觉节奏。",
    },
    "newspaper": {
        "background": "#f1ecdf", "surface": "#fffdf6", "ink": "#1e1d1a", "muted": "#71695c",
        "accent": "#a5362f", "highlight": "#a67a32", "radius": "0px", "border_width": "1px",
        "font": "'Songti SC','STSong','Noto Serif CJK SC','SimSun',Georgia,serif",
        "plot_family": "serif", "plot_fonts": "Songti SC,STSong,Noto Serif CJK SC,SimSun,Georgia",
        "texture": "repeating-linear-gradient(0deg,#3b302604 0,#3b302604 1px,transparent 1px,transparent 4px)",
        "guidance": "报刊编辑风：暖纸色、衬线字体、细版式线、黑红标题和严谨分栏，像高质量知识报纸而非普通卡片。",
    },
    "pixel": {
        "background": "#17152b", "surface": "#272147", "ink": "#f5ead7", "muted": "#aaa1c7",
        "accent": "#ffd166", "highlight": "#58dfc0", "radius": "0px", "border_width": "2px",
        "shadow": "4px 4px 0 #080711", "font": "'SFMono-Regular','Cascadia Mono',Menlo,Consolas,'PingFang SC','Microsoft YaHei',monospace",
        "plot_family": "monospace", "plot_fonts": "SFMono-Regular,Cascadia Mono,Menlo,Consolas,PingFang SC,Microsoft YaHei,monospace",
        "texture": "repeating-linear-gradient(0deg,#ffffff04 0,#ffffff04 1px,transparent 1px,transparent 4px)",
        "guidance": "精致像素风：深色玻璃、可爱等宽字体、阶梯硬边、像素网格、硬阴影与明确高亮，所有图表保持几何精确。",
    },
    "watercolor": {
        "background": "#f5f1e8", "surface": "#fffdf8", "ink": "#38443f", "muted": "#78867e",
        "accent": "#438f83", "highlight": "#d47f6b", "radius": "20px 14px 22px 13px", "border_width": "1px",
        "shadow": "2px 3px 0 #78948618", "font": "'Kaiti SC','STKaiti','KaiTi','Songti SC',serif",
        "plot_family": "serif", "plot_fonts": "Kaiti SC,STKaiti,KaiTi,Songti SC,STSong,SimSun",
        "texture": "radial-gradient(ellipse at 20% 0,#b9d9cd45,transparent 45%),radial-gradient(ellipse at 90% 20%,#efc4b540,transparent 38%)",
        "guidance": "水彩手账风：暖白纸感、青绿与陶土色、柔和不规则边界和手写感字体，保持标注清晰。",
    },
}

THEME_CSS = {
    "anime": ".style-anime .card{border-color:var(--ink)}.style-anime h1,.style-anime h2,.style-anime h3{letter-spacing:.02em}.style-anime button{border:2px solid var(--ink);border-radius:999px;box-shadow:2px 2px 0 var(--ink)}",
    "newspaper": ".style-newspaper body{padding:26px}.style-newspaper .card{border-width:0 0 1px;border-color:var(--ink);padding:20px 4px}.style-newspaper h1,.style-newspaper h2,.style-newspaper h3{line-height:1.25;letter-spacing:.025em}.style-newspaper h1{border-bottom:3px double var(--ink);padding-bottom:10px}",
    "pixel": """
.style-pixel .card{border-color:var(--ink)}
.style-pixel h1,.style-pixel h2,.style-pixel h3{letter-spacing:.04em;text-shadow:2px 2px 0 #080711}
.style-pixel button{border:2px solid var(--ink);border-radius:0;box-shadow:3px 3px 0 #080711}
.style-pixel .wx-stage,.style-pixel .plot{border:2px solid var(--muted);box-shadow:5px 5px 0 #080711}
.style-pixel .wx-graph-card{stroke:var(--ink);stroke-width:2;filter:drop-shadow(4px 4px 0 #080711)}
.style-pixel .wx-graph-badge{stroke:var(--ink);stroke-width:2}
.style-pixel .wx-graph-number{fill:var(--ink)}
.style-pixel .wx-graph-edge{stroke-width:3;stroke-dasharray:7 3;stroke-linecap:square;opacity:.9}
.style-pixel .wx-graph-grid{stroke-width:1;opacity:.18}
.style-pixel .wx-graph-meta{color:var(--highlight);font-weight:700}
.style-pixel .wx-graph-description{fill:var(--ink);opacity:.76}
.style-pixel svg,.style-pixel canvas{image-rendering:pixelated;shape-rendering:crispEdges}
.style-pixel .wx-graph-label,.style-pixel .wx-graph-description{shape-rendering:geometricPrecision}
""",
    "watercolor": ".style-watercolor .card{border-color:var(--muted);border-width:1px 2px 2px 1px}.style-watercolor h1,.style-watercolor h2,.style-watercolor h3{letter-spacing:.035em}",
}


def style_guide(name: str) -> dict[str, str]:
    return {**DEFAULT_TOKENS, **STYLE_GUIDES.get(name, STYLE_GUIDES["textbook"])}


def style_shell(name: str, body: str, css: str, javascript: str) -> str:
    from string import Template

    from .design import DESIGN_CSS, MOTION_JS

    style = style_guide(name)
    template = Template("""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:">
<style>
:root{--bg:$background;--surface:$surface;--ink:$ink;--muted:$muted;--accent:$accent;--highlight:$highlight;--font:$font;--radius:$radius;--border-width:$border_width;--shadow:$shadow;--texture:$texture}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--bg);background-image:var(--texture);color:var(--ink);font-family:var(--font)}body{padding:18px;line-height:1.6}button,input{font:inherit}button{cursor:pointer}.card{background:var(--surface);border:var(--border-width) solid color-mix(in srgb,var(--muted) 45%,transparent);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px}.accent{color:var(--accent)}.highlight{color:var(--highlight)}.muted{color:var(--muted)}$design_css$theme_css$css
</style></head><body class="style-$name">$body<script>try{$motion_js}catch(error){console.error(error)}</script><script>try{$javascript}catch(error){const notice=document.createElement('pre');notice.style.color='var(--highlight)';notice.textContent='交互运行失败：'+error.message;document.body.appendChild(notice)}</script></body></html>""")
    return template.safe_substitute(
        **style, name=name, design_css=DESIGN_CSS, motion_js=MOTION_JS,
        theme_css=THEME_CSS.get(name, ""), body=body, css=css, javascript=javascript,
    )
