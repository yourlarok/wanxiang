from html import escape
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SceneElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "rect", "grid", "arrow", "circle", "line"]
    x: float | None = None
    y: float | None = None
    to_x: float | None = None
    to_y: float | None = None
    width: float | None = None
    height: float | None = None
    cx: float | None = None
    cy: float | None = None
    r: float | None = None
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
    size: float = Field(default=16, ge=8, le=80)

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
        return self


class SceneSpec(BaseModel):
    width: int = Field(default=900, ge=400, le=1800)
    height: int = Field(default=520, ge=240, le=1400)
    elements: list[SceneElement] = Field(min_length=1, max_length=300)


def _paint(role: str) -> tuple[str, str]:
    if role in {"accent", "highlight"}:
        return f"var(--{role})", "var(--ink)"
    if role in {"ink", "muted", "title"}:
        return "none", "var(--muted)" if role == "muted" else "var(--ink)"
    return "var(--surface)", "var(--muted)"


def _text(element: SceneElement) -> str:
    content = escape(element.text or element.label)
    weight = 700 if element.role == "title" else 500
    fill = "var(--accent)" if element.role == "accent" else "var(--highlight)" if element.role == "highlight" else "var(--muted)" if element.role == "muted" else "var(--ink)"
    return f'<text x="{element.x}" y="{element.y}" font-size="{element.size}" font-weight="{weight}" text-anchor="{element.align}" fill="{fill}">{content}</text>'


def render_scene(spec: SceneSpec) -> str:
    parts = [
        f'<svg class="scene" viewBox="0 0 {spec.width} {spec.height}" role="img" xmlns="http://www.w3.org/2000/svg">',
        '<defs><marker id="scene-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="var(--accent)"/></marker></defs>',
    ]
    for element in spec.elements:
        if element.type == "text":
            parts.append(_text(element))
        elif element.type == "rect":
            fill, stroke = _paint(element.role)
            opacity = ' fill-opacity="0.2"' if element.role in {"accent", "highlight"} else ""
            parts.append(f'<rect x="{element.x}" y="{element.y}" width="{element.width}" height="{element.height}" rx="{element.rx}" fill="{fill}"{opacity} stroke="{stroke}" stroke-opacity="0.5"/>')
            if element.label:
                parts.append(f'<text x="{element.x + 12}" y="{element.y + 25}" font-size="14" fill="var(--ink)">{escape(element.label)}</text>')
        elif element.type == "grid":
            fill, stroke = _paint(element.role)
            for index in range((element.rows or 1) * (element.columns or 1)):
                row, column = divmod(index, element.columns or 1)
                x = (element.x or 0) + column * (element.cell_width + element.gap)
                y = (element.y or 0) + row * (element.cell_height + element.gap)
                parts.append(f'<rect x="{x}" y="{y}" width="{element.cell_width}" height="{element.cell_height}" rx="5" fill="{fill}" stroke="{stroke}" stroke-opacity="0.55"/>')
                if index < len(element.labels):
                    parts.append(f'<text x="{x + element.cell_width / 2}" y="{y + element.cell_height / 2 + 5}" font-size="14" text-anchor="middle" fill="var(--ink)">{escape(element.labels[index])}</text>')
        elif element.type in {"arrow", "line"}:
            marker = ' marker-end="url(#scene-arrow)"' if element.type == "arrow" else ""
            parts.append(f'<line x1="{element.x}" y1="{element.y}" x2="{element.to_x}" y2="{element.to_y}" stroke="var(--accent)" stroke-width="2"{marker}/>')
            if element.label:
                parts.append(f'<text x="{((element.x or 0) + (element.to_x or 0)) / 2}" y="{((element.y or 0) + (element.to_y or 0)) / 2 - 8}" font-size="12" text-anchor="middle" fill="var(--muted)">{escape(element.label)}</text>')
        elif element.type == "circle":
            fill, stroke = _paint(element.role)
            opacity = ' fill-opacity="0.35"' if element.role in {"accent", "highlight"} else ""
            parts.append(f'<circle cx="{element.cx}" cy="{element.cy}" r="{element.r}" fill="{fill}"{opacity} stroke="{stroke}"/>')
            if element.label:
                parts.append(f'<text x="{element.cx}" y="{element.cy + 5}" font-size="14" text-anchor="middle" fill="var(--ink)">{escape(element.label)}</text>')
    parts.append("</svg>")
    return "".join(parts)
