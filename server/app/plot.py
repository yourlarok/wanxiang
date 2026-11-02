import itertools
import re
from io import StringIO
from typing import Literal

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .styles import style_guide


Color = str
NumberList = list[float]


class VizModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PlotSeries(VizModel):
    kind: Literal["line", "scatter", "bar", "bar3d", "voxels", "surface"]
    label: str = Field(default="", max_length=80)
    x: NumberList = Field(default_factory=list, max_length=5000)
    y: NumberList = Field(default_factory=list, max_length=5000)
    z: NumberList = Field(default_factory=list, max_length=5000)
    values: list[NumberList] = Field(default_factory=list, max_length=200)
    dx: float | NumberList = 0.8
    dy: float | NumberList = 0.8
    dz: float | NumberList = 0.8
    shape: list[int] = Field(default_factory=list, max_length=3)
    coordinates: list[list[int]] = Field(default_factory=list, max_length=5000)
    origin: NumberList = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    cell_size: NumberList = Field(default_factory=lambda: [0.82, 0.82, 0.82], min_length=3, max_length=3)
    color: Color = "accent"
    colors: list[Color] = Field(default_factory=list, max_length=32)
    color_by: Literal["index", "x", "y", "z"] = "index"
    size: float = Field(default=36, gt=0, le=500)
    linewidth: float = Field(default=2, gt=0, le=20)
    alpha: float = Field(default=0.92, gt=0, le=1)
    cmap: Literal["viridis", "plasma", "coolwarm", "cividis", "magma"] = "viridis"

    @field_validator("color", "colors", check_fields=False)
    @classmethod
    def validate_color(cls, value):
        values = value if isinstance(value, list) else [value]
        for color in values:
            if color not in {"accent", "highlight", "ink", "muted"} and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("颜色必须是语义色或六位十六进制颜色")
        return value

    @model_validator(mode="after")
    def validate_series(self):
        if self.kind in {"line", "scatter", "bar"} and not self.y:
            raise ValueError(f"{self.kind} 需要 y 数据")
        if self.x and len(self.x) != len(self.y):
            raise ValueError("x 与 y 数据长度必须一致")
        if self.kind == "scatter" and self.z and len(self.z) != len(self.y):
            raise ValueError("三维散点的 x、y、z 数据长度必须一致")
        if self.kind == "bar3d":
            if not self.x or not self.y or not self.z or len({len(self.x), len(self.y), len(self.z)}) != 1:
                raise ValueError("bar3d 需要等长的 x、y、z 坐标")
            for size in (self.dx, self.dy, self.dz):
                if isinstance(size, list) and len(size) != len(self.x):
                    raise ValueError("bar3d 尺寸必须与坐标数量一致")
        if self.kind == "voxels":
            if not self.shape and not self.coordinates:
                raise ValueError("voxels 需要 shape 或 coordinates")
            if self.shape and (len(self.shape) != 3 or any(size < 1 or size > 64 for size in self.shape)):
                raise ValueError("voxels shape 必须包含三个 1–64 的维度")
            if self.shape and self.shape[0] * self.shape[1] * self.shape[2] > 8000:
                raise ValueError("voxels 总单元数不能超过 8000")
            if any(len(point) != 3 or any(value < 0 for value in point) for point in self.coordinates):
                raise ValueError("voxels coordinates 必须是非负三维整数坐标")
            if self.shape:
                for point in self.coordinates:
                    if any(value >= self.shape[index] for index, value in enumerate(point)):
                        raise ValueError("voxels 坐标超出 shape")
            if any(size <= 0 or size > 1 for size in self.cell_size):
                raise ValueError("voxels cell_size 必须位于 0–1 之间")
        if self.kind == "surface":
            if not self.values or not self.values[0]:
                raise ValueError("surface 需要 values 二维高度数据")
            columns = len(self.values[0])
            if any(len(row) != columns for row in self.values):
                raise ValueError("surface values 必须是矩形网格")
            if len(self.values) * columns > 10000:
                raise ValueError("surface 网格不能超过 10000 个点")
            if self.x and len(self.x) != columns:
                raise ValueError("surface x 长度必须等于 values 列数")
            if self.y and len(self.y) != len(self.values):
                raise ValueError("surface y 长度必须等于 values 行数")
        return self

    @property
    def is_3d(self) -> bool:
        return self.kind in {"bar3d", "voxels", "surface"} or bool(self.z)


class PlotPanel(VizModel):
    title: str = Field(default="", max_length=120)
    x_label: str = Field(default="", max_length=80)
    y_label: str = Field(default="", max_length=80)
    z_label: str = Field(default="", max_length=80)
    projection: Literal["auto", "2d", "3d"] = "auto"
    view_elev: float = Field(default=24, ge=-90, le=90)
    view_azim: float = Field(default=-55, ge=-360, le=360)
    legend: bool = False
    grid: bool = True
    series: list[PlotSeries] = Field(min_length=1, max_length=16)


class PlotSpec(VizModel):
    rows: int = Field(default=1, ge=1, le=4)
    columns: int = Field(default=1, ge=1, le=4)
    width: float = Field(default=10, ge=4, le=20)
    height: float = Field(default=6, ge=3, le=16)
    dpi: int = Field(default=120, ge=72, le=192)
    panels: list[PlotPanel] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_layout(self):
        if len(self.panels) > self.rows * self.columns:
            raise ValueError("panels 数量不能超过 rows × columns")
        return self


def _configure_fonts() -> None:
    available = {font.name for font in font_manager.fontManager.ttflist}
    candidates = [
        "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC",
        "SimHei", "Arial Unicode MS", "WenQuanYi Micro Hei",
    ]
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = [name for name in candidates if name in available] + ["DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["svg.fonttype"] = "none"


_configure_fonts()


def _color(value: str, style: dict[str, str]) -> str:
    return style.get(value, value)


def _palette(series: PlotSeries, style: dict[str, str]) -> list[str]:
    return [_color(value, style) for value in (series.colors or [series.color])]


def _colors(series: PlotSeries, coordinates: list[tuple[float, float, float]], style: dict[str, str]) -> list[str]:
    palette = _palette(series, style)
    if len(palette) == 1:
        return palette * len(coordinates)
    axis = {"x": 0, "y": 1, "z": 2}.get(series.color_by)
    if axis is None:
        return [palette[index % len(palette)] for index in range(len(coordinates))]
    return [palette[int(point[axis]) % len(palette)] for point in coordinates]


def _size(value: float | NumberList, count: int) -> float | NumberList:
    if isinstance(value, list):
        return value
    return [value] * count


def _draw_series(ax, series: PlotSeries, is_3d: bool, style: dict[str, str]) -> None:
    x = series.x or list(range(len(series.y)))
    color = _color(series.color, style)
    if series.kind == "line":
        ax.plot(x, series.y, label=series.label or None, color=color, linewidth=series.linewidth, alpha=series.alpha)
    elif series.kind == "scatter":
        if is_3d:
            ax.scatter(x, series.y, series.z, label=series.label or None, color=color, s=series.size, alpha=series.alpha)
        else:
            ax.scatter(x, series.y, label=series.label or None, color=color, s=series.size, alpha=series.alpha)
    elif series.kind == "bar":
        ax.bar(x, series.y, label=series.label or None, color=color, alpha=series.alpha)
    elif series.kind == "bar3d":
        coordinates = list(zip(series.x, series.y, series.z))
        ax.bar3d(
            series.x, series.y, series.z, _size(series.dx, len(x)), _size(series.dy, len(x)), _size(series.dz, len(x)),
            color=_colors(series, coordinates, style), alpha=series.alpha, shade=True, edgecolor=style["background"], linewidth=0.25,
        )
    elif series.kind == "voxels":
        points = series.coordinates or list(itertools.product(*(range(size) for size in series.shape)))
        coordinates = [tuple(float(value) for value in point) for point in points]
        xs = [point[0] + series.origin[0] for point in coordinates]
        ys = [point[1] + series.origin[1] for point in coordinates]
        zs = [point[2] + series.origin[2] for point in coordinates]
        ax.bar3d(
            xs, ys, zs, series.cell_size[0], series.cell_size[1], series.cell_size[2],
            color=_colors(series, coordinates, style), alpha=series.alpha, shade=True, edgecolor=style["background"], linewidth=0.3,
        )
        if series.shape:
            ax.set_xlim(0, series.shape[0])
            ax.set_ylim(0, series.shape[1])
            ax.set_zlim(0, series.shape[2])
    elif series.kind == "surface":
        rows = len(series.values)
        columns = len(series.values[0])
        xs = series.x or list(range(columns))
        ys = series.y or list(range(rows))
        mesh_x, mesh_y = np.meshgrid(xs, ys)
        ax.plot_surface(mesh_x, mesh_y, np.asarray(series.values), cmap=series.cmap, alpha=series.alpha, linewidth=0, antialiased=True)


def _style_axis(ax, panel: PlotPanel, is_3d: bool, style: dict[str, str]) -> None:
    ax.set_title(panel.title, color=style["ink"], fontsize=11, fontweight=600, pad=14)
    ax.set_xlabel(panel.x_label, color=style["muted"], fontsize=9, labelpad=8)
    ax.set_ylabel(panel.y_label, color=style["muted"], fontsize=9, labelpad=8)
    ax.tick_params(colors=style["muted"], labelsize=8)
    ax.grid(panel.grid, color=style["muted"], alpha=0.2, linewidth=0.7)
    for spine in ax.spines.values():
        spine.set_color(style["muted"])
        spine.set_alpha(0.35)
    if is_3d:
        ax.set_zlabel(panel.z_label, color=style["muted"], fontsize=9, labelpad=8)
        ax.view_init(elev=panel.view_elev, azim=panel.view_azim)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.set_facecolor(style["surface"])
            axis.pane.set_alpha(0.28)
            axis.pane.set_edgecolor(style["muted"])
            if any(series.kind in {"bar3d", "voxels"} for series in panel.series):
                axis.set_major_locator(MaxNLocator(integer=True))
        ax.set_box_aspect(None, zoom=0.88)
    if panel.legend and any(series.label for series in panel.series):
        legend = ax.legend(frameon=False, fontsize=8)
        for text in legend.get_texts():
            text.set_color(style["ink"])


def render_plot(spec: PlotSpec, style_name: str = "textbook") -> str:
    style = style_guide(style_name)
    figure = plt.figure(
        figsize=(spec.width, spec.height), dpi=spec.dpi, facecolor=style["background"], layout="constrained",
    )
    try:
        for index, panel in enumerate(spec.panels):
            is_3d = panel.projection == "3d" or (panel.projection == "auto" and any(series.is_3d for series in panel.series))
            ax = figure.add_subplot(spec.rows, spec.columns, index + 1, projection="3d" if is_3d else None)
            ax.set_facecolor(style["background"])
            for series in panel.series:
                _draw_series(ax, series, is_3d, style)
            _style_axis(ax, panel, is_3d, style)
        output = StringIO()
        figure.savefig(output, format="svg", dpi=spec.dpi, facecolor=style["background"], bbox_inches="tight", pad_inches=0.2)
        svg = output.getvalue()
        svg = svg[svg.index("<svg"):]
        return re.sub(r'(<svg\b[^>]*?)width="[^"]+"\s+height="[^"]+"', r'\1width="100%"', svg, count=1)
    finally:
        plt.close(figure)
