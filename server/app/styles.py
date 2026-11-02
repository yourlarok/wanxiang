STYLE_GUIDES = {
    "textbook": {
        "background": "#0e131c",
        "surface": "#171f2c",
        "ink": "#e7ecf4",
        "muted": "#8b98ab",
        "accent": "#a894ff",
        "highlight": "#f0a660",
        "guidance": "教材式解释：先给直观例子，再给定义；使用卡片、嵌套框、标注和短句，避免装饰性大段文字。",
    },
    "blueprint": {
        "background": "#0b1c2b",
        "surface": "#102a3e",
        "ink": "#d9edf5",
        "muted": "#83a8ba",
        "accent": "#63c7e6",
        "highlight": "#f2c879",
        "guidance": "蓝图式技术表达：细线、网格、精确标注、坐标和构造关系，减少无意义渐变。",
    },
    "minimal": {
        "background": "#f5f4ef",
        "surface": "#ffffff",
        "ink": "#20242a",
        "muted": "#68707a",
        "accent": "#4f62c9",
        "highlight": "#c96942",
        "guidance": "极简教学表达：大量留白、单一强调色、少而准的标注，优先内容层级而非卡片堆叠。",
    },
    "chalk": {
        "background": "#18302b",
        "surface": "#203b34",
        "ink": "#edf0dc",
        "muted": "#b0bba6",
        "accent": "#e7d88c",
        "highlight": "#e89b7b",
        "guidance": "黑板推导风格：手算步骤、圈注、箭头与分项解释，适合公式和概念直觉。",
    },
}


def style_guide(name: str) -> dict[str, str]:
    return STYLE_GUIDES.get(name, STYLE_GUIDES["textbook"])


def style_shell(name: str, body: str, css: str, javascript: str) -> str:
    from string import Template

    style = style_guide(name)
    template = Template("""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:">
<style>
:root{--bg:$background;--surface:$surface;--ink:$ink;--muted:$muted;--accent:$accent;--highlight:$highlight}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--bg);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif}body{padding:18px;line-height:1.6}button,input{font:inherit}button{cursor:pointer}.card{background:var(--surface);border:1px solid color-mix(in srgb,var(--muted) 30%,transparent);border-radius:12px;padding:16px}.accent{color:var(--accent)}.highlight{color:var(--highlight)}.muted{color:var(--muted)}$css
</style></head><body>$body<script>try{$javascript}catch(error){const notice=document.createElement('pre');notice.style.color='var(--highlight)';notice.textContent='交互运行失败：'+error.message;document.body.appendChild(notice)}</script></body></html>""")
    return template.safe_substitute(**style, body=body, css=css, javascript=javascript)
