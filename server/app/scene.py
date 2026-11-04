import re
from html import escape
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SceneElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "rect", "grid", "arrow", "circle", "line", "path", "ellipse", "polygon"]
    id: str = Field(default="", max_length=64, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$|^$")
    x: float | None = None
    y: float | None = None
    to_x: float | None = None
    to_y: float | None = None
    width: float | None = None
    height: float | None = None
    cx: float | None = None
    cy: float | None = None
    r: float | None = None
    rx_radius: float | None = Field(default=None, gt=0, le=1000)
    ry_radius: float | None = Field(default=None, gt=0, le=1000)
    d: str = Field(default="", max_length=4000)
    points: str = Field(default="", max_length=2000)
    rows: int | None = Field(default=None, ge=1, le=20)
    columns: int | None = Field(default=None, ge=1, le=20)
    cell_width: float = Field(default=42, gt=4, le=300)
    cell_height: float = Field(default=42, gt=4, le=300)
    gap: float = Field(default=6, ge=0, le=80)
    rx: float = Field(default=10, ge=0, le=100)
    text: str = Field(default="", max_length=300)
    label: str = Field(default="", max_length=100)
    labels: list[str] = Field(default_factory=list, max_length=400)
    role: Literal["surface", "accent", "highlight", "ink", "muted", "title"] = "surface"
    align: Literal["start", "middle", "end"] = "start"
    size: float = Field(default=16, ge=8, le=100)
    weight: int = Field(default=500, ge=400, le=800)
    tracking: float = Field(default=0, ge=-2, le=12)
    line_height: float = Field(default=1.35, ge=1, le=2.5)
    layer: int = Field(default=0, ge=-20, le=20)
    opacity: float = Field(default=1, ge=0, le=1)
    fill_opacity: float | None = Field(default=None, ge=0, le=1)
    stroke_width: float = Field(default=1.5, ge=0, le=20)
    rotate: float = Field(default=0, ge=-360, le=360)
    bend: float = Field(default=0, ge=-400, le=400)
    solid: bool = False
    shadow: bool = False
    dashed: bool = False
    motion: Literal["none", "enter", "rise", "draw", "pulse", "float"] = "none"
    delay: int = Field(default=0, ge=0, le=2000)

    @model_validator(mode="after")
    def validate_geometry(self):
        if self.type in {"text", "rect", "grid", "arrow", "line"} and (self.x is None or self.y is None):
            raise ValueError("场景元素缺少坐标")
        if self.type == "rect" and (not self.width or not self.height):
            raise ValueError("矩形缺少尺寸")
        if self.type == "grid" and (not self.rows or not self.columns):
            raise ValueError("网格缺少行列")
        if self.type in {"arrow", "line"} and (self.to_x is None or self.to_y is None):
            raise ValueError("连线缺少终点")
        if self.type == "circle" and (self.cx is None or self.cy is None or not self.r):
            raise ValueError("圆形缺少圆心或半径")
        if self.type == "ellipse" and (self.cx is None or self.cy is None or not self.rx_radius or not self.ry_radius):
            raise ValueError("椭圆缺少圆心或半径")
        if self.type == "path" and (not self.d or not re.fullmatch(r"[a-zA-Z0-9.,+\-\s]+", self.d)):
            raise ValueError("路径数据为空或包含非法字符")
        if self.type == "polygon" and (not self.points or not re.fullmatch(r"[0-9.,+\-\s]+", self.points)):
            raise ValueError("多边形坐标为空或包含非法字符")
        return self


class SceneSpec(BaseModel):
    width: int = Field(default=900, ge=400, le=1800)
    height: int = Field(default=520, ge=240, le=1400)
    texture: Literal["none", "grid", "dots", "glow"] = "glow"
    animated: bool = True
    elements: list[SceneElement] = Field(min_length=1, max_length=300)


def _paint(role: str) -> tuple[str, str]:
    if role in {"accent", "highlight"}:
        return f"var(--{role})", "var(--ink)"
    if role in {"ink", "muted", "title"}:
        return "none", "var(--muted)" if role == "muted" else "var(--ink)"
    return "var(--surface)", "var(--muted)"


def _attributes(element: SceneElement, cx: float | None = None, cy: float | None = None) -> str:
    attributes = []
    if element.id:
        attributes.append(f'id="{element.id}"')
    if element.motion != "none":
        attributes.append(f'data-motion="{element.motion}"')
    if element.delay:
        attributes.append(f'style="--delay:{element.delay}ms"')
    if element.opacity != 1:
        attributes.append(f'opacity="{element.opacity}"')
    if element.shadow:
        attributes.append('filter="url(#scene-shadow)"')
    if element.dashed:
        attributes.append('stroke-dasharray="7 7"')
    if element.rotate and cx is not None and cy is not None:
        attributes.append(f'transform="rotate({element.rotate} {cx} {cy})"')
    return (" " + " ".join(attributes)) if attributes else ""


def _text(element: SceneElement) -> str:
    content = escape(element.text or element.label)
    fill = "var(--accent)" if element.role == "accent" else "var(--highlight)" if element.role == "highlight" else "var(--muted)" if element.role == "muted" else "var(--ink)"
    weight = 720 if element.role == "title" else element.weight
    lines = content.splitlines() or [""]
    spans = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else element.size * element.line_height
        spans.append(f'<tspan x="{element.x}" dy="{dy}">{line}</tspan>')
    return f'<text x="{element.x}" y="{element.y}" font-size="{element.size}" font-weight="{weight}" letter-spacing="{element.tracking}" text-anchor="{element.align}" fill="{fill}"{_attributes(element, element.x, element.y)}>{"".join(spans)}</text>'


def _fill(element: SceneElement, role: str) -> tuple[str, str]:
    fill = f"var(--{element.role})" if element.solid and element.role in {"accent", "highlight"} else role
    opacity = element.fill_opacity
    if opacity is None:
        opacity = 0.18 if element.role in {"accent", "highlight"} and not element.solid else 1
    return fill, f' fill-opacity="{opacity}"'


def render_scene(spec: SceneSpec) -> str:
    parts = [
        f'<svg class="scene wx-scene" viewBox="0 0 {spec.width} {spec.height}" role="img" xmlns="http://www.w3.org/2000/svg">',
        '''<defs>
        <linearGradient id="scene-accent" x1="0" y1="0" x2="1" y2="1"><stop stop-color="var(--accent)"/><stop offset="1" stop-color="var(--highlight)"/></linearGradient>
        <radialGradient id="scene-glow"><stop stop-color="var(--accent)" stop-opacity=".13"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></radialGradient>
        <pattern id="scene-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="var(--muted)" stroke-opacity=".09" stroke-width="1"/></pattern>
        <pattern id="scene-dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="var(--muted)" fill-opacity=".16"/></pattern>
        <filter id="scene-shadow" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#000" flood-opacity=".18"/></filter>
        <marker id="scene-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="var(--accent)"/></marker>
        </defs>''',
    ]
    if spec.texture == "glow":
        parts.append(f'<rect width="{spec.width}" height="{spec.height}" fill="url(#scene-glow)"/>')
    elif spec.texture in {"grid", "dots"}:
        parts.append(f'<rect width="{spec.width}" height="{spec.height}" fill="url(#scene-{spec.texture})"/>')
    for element in sorted(spec.elements, key=lambda item: item.layer):
        motion = element.motion if spec.animated else "none"
        element = element.model_copy(update={"motion": motion})
        if element.type == "text":
            parts.append(_text(element))
        elif element.type == "rect":
            role, stroke = _paint(element.role)
            fill, opacity = _fill(element, role)
            parts.append(f'<rect x="{element.x}" y="{element.y}" width="{element.width}" height="{element.height}" rx="{element.rx}" fill="{fill}"{opacity} stroke="{stroke}" stroke-width="{element.stroke_width}" stroke-opacity="0.5"{_attributes(element, (element.x or 0) + (element.width or 0) / 2, (element.y or 0) + (element.height or 0) / 2)}/>')
            if element.label:
                label_fill = "var(--bg)" if element.solid else "var(--ink)"
                parts.append(f'<text x="{element.x + 12}" y="{element.y + 25}" font-size="14" fill="{label_fill}">{escape(element.label)}</text>')
        elif element.type == "grid":
            role, stroke = _paint(element.role)
            fill, opacity = _fill(element, role)
            for index in range((element.rows or 1) * (element.columns or 1)):
                row, column = divmod(index, element.columns or 1)
                x = (element.x or 0) + column * (element.cell_width + element.gap)
                y = (element.y or 0) + row * (element.cell_height + element.gap)
                parts.append(f'<rect x="{x}" y="{y}" width="{element.cell_width}" height="{element.cell_height}" rx="5" fill="{fill}"{opacity} stroke="{stroke}" stroke-width="{element.stroke_width}" stroke-opacity="0.55"{_attributes(element)}/>')
                if index < len(element.labels):
                    parts.append(f'<text x="{x + element.cell_width / 2}" y="{y + element.cell_height / 2 + 5}" font-size="14" text-anchor="middle" fill="var(--ink)">{escape(element.labels[index])}</text>')
        elif element.type in {"arrow", "line"}:
            marker = ' marker-end="url(#scene-arrow)"' if element.type == "arrow" else ""
            if element.bend:
                control_x = ((element.x or 0) + (element.to_x or 0)) / 2
                control_y = ((element.y or 0) + (element.to_y or 0)) / 2 + element.bend
                parts.append(f'<path d="M{element.x},{element.y} Q{control_x},{control_y} {element.to_x},{element.to_y}" fill="none" stroke="var(--accent)" stroke-width="{element.stroke_width}"{marker}{_attributes(element)}/>')
            else:
                parts.append(f'<line x1="{element.x}" y1="{element.y}" x2="{element.to_x}" y2="{element.to_y}" stroke="var(--accent)" stroke-width="{element.stroke_width}"{marker}{_attributes(element)}/>')
            if element.label:
                parts.append(f'<text x="{((element.x or 0) + (element.to_x or 0)) / 2}" y="{((element.y or 0) + (element.to_y or 0)) / 2 + element.bend / 2 - 8}" font-size="12" text-anchor="middle" fill="var(--muted)">{escape(element.label)}</text>')
        elif element.type == "circle":
            role, stroke = _paint(element.role)
            fill, opacity = _fill(element, role)
            parts.append(f'<circle cx="{element.cx}" cy="{element.cy}" r="{element.r}" fill="{fill}"{opacity} stroke="{stroke}" stroke-width="{element.stroke_width}"{_attributes(element, element.cx, element.cy)}/>')
            if element.label:
                parts.append(f'<text x="{element.cx}" y="{element.cy + 5}" font-size="14" text-anchor="middle" fill="var(--ink)">{escape(element.label)}</text>')
        elif element.type == "ellipse":
            role, stroke = _paint(element.role)
            fill, opacity = _fill(element, role)
            parts.append(f'<ellipse cx="{element.cx}" cy="{element.cy}" rx="{element.rx_radius}" ry="{element.ry_radius}" fill="{fill}"{opacity} stroke="{stroke}" stroke-width="{element.stroke_width}"{_attributes(element, element.cx, element.cy)}/>')
        elif element.type == "path":
            _, stroke = _paint(element.role)
            color = f"var(--{element.role})" if element.role in {"accent", "highlight"} else stroke
            parts.append(f'<path d="{element.d}" fill="none" stroke="{color}" stroke-width="{element.stroke_width}" stroke-linecap="round" stroke-linejoin="round"{_attributes(element)}/>')
        elif element.type == "polygon":
            role, stroke = _paint(element.role)
            fill, opacity = _fill(element, role)
            parts.append(f'<polygon points="{element.points}" fill="{fill}"{opacity} stroke="{stroke}" stroke-width="{element.stroke_width}" stroke-linejoin="round"{_attributes(element)}/>')
    parts.append("</svg>")
    return "".join(parts)
