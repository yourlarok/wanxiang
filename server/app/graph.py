import html
import math
import unicodedata

from .artifacts import GraphPayload


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in text)


def wrap_text(text: str, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    current_width = 0
    for char in text.strip():
        if char == "\n":
            lines.append(current)
            current = ""
            current_width = 0
            continue
        char_width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if current and current_width + char_width > width:
            lines.append(current)
            current = char
            current_width = char_width
        else:
            current += char
            current_width += char_width
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)
    consumed = "".join(lines)
    compact_source = text.strip().replace("\n", "")
    if len(consumed) < len(compact_source) and lines:
        lines[-1] = lines[-1][:-1] + "…" if len(lines[-1]) > 1 else "…"
    return lines or [""]


def text_lines(lines: list[str], x: float, y: float, class_name: str, line_height: float) -> str:
    spans = "".join(
        f'<tspan x="{x:g}" dy="{0 if index == 0 else line_height:g}">{html.escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text class="{class_name}" x="{x:g}" y="{y:g}">{spans}</text>'


def edge_points(source: dict[str, float], target: dict[str, float]) -> tuple[float, float, float, float]:
    source_x = source["x"] + source["w"] / 2
    source_y = source["y"] + source["h"] / 2
    target_x = target["x"] + target["w"] / 2
    target_y = target["y"] + target["h"] / 2
    dx = target_x - source_x
    dy = target_y - source_y
    if not dx and not dy:
        return source_x, source_y, target_x, target_y
    source_scale = min(
        (source["w"] / 2 + 5) / abs(dx) if dx else math.inf,
        (source["h"] / 2 + 5) / abs(dy) if dy else math.inf,
    )
    target_scale = min(
        (target["w"] / 2 + 8) / abs(dx) if dx else math.inf,
        (target["h"] / 2 + 8) / abs(dy) if dy else math.inf,
    )
    return (
        source_x + dx * source_scale,
        source_y + dy * source_scale,
        target_x - dx * target_scale,
        target_y - dy * target_scale,
    )


def render_graph(graph: GraphPayload) -> tuple[str, str]:
    count = len(graph.nodes)
    columns = 1 if count == 1 else 2 if count <= 4 else 3
    card_width = 300 if columns < 3 else 276
    gap = 28
    padding = 34
    wrapped = {
        node.id: (
            wrap_text(node.label, 27 if columns == 3 else 34, 2),
            wrap_text(node.description, 43 if columns == 3 else 54, 4),
        )
        for node in graph.nodes
    }
    card_height = max(
        122,
        max(64 + len(label) * 20 + len(description) * 20 for label, description in wrapped.values()),
    )
    rows = math.ceil(count / columns)
    width = padding * 2 + columns * card_width + (columns - 1) * gap
    height = padding * 2 + rows * card_height + (rows - 1) * gap
    boxes: dict[str, dict[str, float]] = {}
    for index, node in enumerate(graph.nodes):
        row, column = divmod(index, columns)
        if graph.kind == "process" and row % 2:
            column = columns - 1 - column
        boxes[node.id] = {
            "x": padding + column * (card_width + gap),
            "y": padding + row * (card_height + gap),
            "w": card_width,
            "h": card_height,
        }

    edges = []
    for edge in graph.edges:
        source = boxes[edge.source]
        target = boxes[edge.target]
        x1, y1, x2, y2 = edge_points(source, target)
        edges.append(
            f'<path class="wx-graph-edge" d="M{x1:g},{y1:g} L{x2:g},{y2:g}" marker-end="url(#wx-arrow)"/>'
        )
        if edge.label:
            label_x = (x1 + x2) / 2
            label_y = (y1 + y2) / 2 - 8
            label_width = min(150, display_width(edge.label) * 6 + 18)
            edges.append(
                f'<rect class="wx-graph-edge-label-bg" x="{label_x - label_width / 2:g}" y="{label_y - 13:g}" '
                f'width="{label_width:g}" height="21" rx="10"/>'
                f'<text class="wx-graph-edge-label" x="{label_x:g}" y="{label_y + 2:g}" text-anchor="middle">{html.escape(edge.label)}</text>'
            )

    nodes = []
    for index, node in enumerate(graph.nodes):
        box = boxes[node.id]
        x, y = box["x"], box["y"]
        labels, descriptions = wrapped[node.id]
        label_y = y + 39 + (len(labels) - 1) * 5
        description_y = label_y + 28 + (len(labels) - 1) * 20
        badge = f"{index + 1:02d}"
        nodes.append(f'''<g class="wx-graph-node" data-motion="enter" style="--delay:{index * 65}ms">
<rect class="wx-graph-card" x="{x:g}" y="{y:g}" width="{card_width}" height="{card_height}" rx="16"/>
<rect class="wx-graph-accent" x="{x:g}" y="{y:g}" width="4" height="{card_height}" rx="2"/>
<rect class="wx-graph-badge" x="{x + 12:g}" y="{y + 14:g}" width="30" height="30" rx="15"/>
<text class="wx-graph-number" x="{x + 27:g}" y="{y + 33:g}" text-anchor="middle">{badge}</text>
{text_lines(labels, x + 52, label_y, "wx-graph-label", 20)}
{text_lines(descriptions, x + 20, description_y, "wx-graph-description", 20)}
</g>''')

    body = f'''<main class="wx-graph-wrap" aria-label="{html.escape('流程图' if graph.kind == 'process' else '关系图')}">
<div class="wx-graph-meta"><span>{'PROCESS / 流程' if graph.kind == 'process' else 'CONCEPT MAP / 关系'}</span><b>{count} 个节点 · {len(graph.edges)} 条连接</b></div>
<svg class="wx-graph-canvas" viewBox="0 0 {width} {height}" role="img" aria-label="可视化关系图">
<defs>
<pattern id="wx-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" class="wx-graph-grid"/></pattern>
<marker id="wx-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" class="wx-graph-arrow"/></marker>
</defs>
<rect class="wx-graph-bg" width="{width}" height="{height}" fill="url(#wx-grid)" rx="20"/>
<g>{''.join(edges)}</g>
<g>{''.join(nodes)}</g>
</svg></main>'''
    css = """
.wx-graph-wrap{width:100%;max-width:1080px;margin:0 auto}
.wx-graph-meta{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:0 2px 14px;color:var(--muted);font-size:10px;letter-spacing:.12em}
.wx-graph-meta b{font-weight:500;letter-spacing:0;white-space:nowrap}
.wx-graph-canvas{display:block;width:100%;height:auto;overflow:visible}
.wx-graph-bg{rx:var(--radius)}
.wx-graph-grid{fill:none;stroke:var(--muted);stroke-width:.55;opacity:.12}
.wx-graph-edge{fill:none;stroke:var(--accent);stroke-width:2;opacity:.68;stroke-linecap:round}
.wx-graph-arrow{fill:var(--accent);opacity:.9}
.wx-graph-edge-label-bg{fill:var(--bg);stroke:color-mix(in srgb,var(--accent) 30%,transparent);rx:var(--radius)}
.wx-graph-edge-label{fill:var(--accent);font-family:var(--font);font-size:10px}
.wx-graph-card{fill:var(--surface);stroke:color-mix(in srgb,var(--muted) 38%,transparent);stroke-width:1;filter:drop-shadow(0 8px 12px #00000018);rx:var(--radius)}
.wx-graph-accent{fill:var(--accent);rx:var(--radius)}
.wx-graph-badge{fill:color-mix(in srgb,var(--accent) 18%,var(--surface));stroke:var(--accent);stroke-width:1;rx:var(--radius)}
.wx-graph-number{fill:var(--accent);font-family:var(--font);font-size:11px;font-weight:750;font-variant-numeric:tabular-nums}
.wx-graph-label{fill:var(--ink);font-family:var(--font);font-size:16px;font-weight:700}
.wx-graph-description{fill:var(--muted);font-family:var(--font);font-size:12px;font-weight:400}
"""
    return body, css
