from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisualizationRequest(BaseModel):
    text: str | None = Field(default=None, max_length=20_000)
    image_base64: str | None = Field(default=None, max_length=20_000_000)
    preference: Literal["auto", "concept", "process", "formula", "interactive"] = "auto"
    style: Literal["textbook", "blueprint", "minimal", "chalk"] = "textbook"

    @model_validator(mode="after")
    def require_content(self):
        if not (self.text and self.text.strip()) and not self.image_base64:
            raise ValueError("请提供文本或截图")
        return self


class VisualNode(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1_000)


class VisualEdge(BaseModel):
    source: str
    target: str
    label: str = Field(default="", max_length=80)


class GraphPayload(BaseModel):
    kind: Literal["concept", "process"] = "concept"
    nodes: list[VisualNode] = Field(min_length=1, max_length=100)
    edges: list[VisualEdge] = Field(default_factory=list, max_length=200)


class VariableSpec(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    meaning: str = Field(default="", max_length=200)


class FormulaPayload(BaseModel):
    latex: str = Field(min_length=1, max_length=4_000)
    variables: list[VariableSpec] = Field(default_factory=list)


class HtmlPayload(BaseModel):
    body: str = Field(min_length=1, max_length=150_000)
    css: str = Field(default="", max_length=50_000)
    javascript: str = Field(default="", max_length=80_000)
    document: str = ""


class Verification(BaseModel):
    passed: bool
    checks: list[str] = Field(default_factory=list)
    repairs: int = 0


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["2.0"] = "2.0"
    artifact_type: Literal["html", "graph", "formula"]
    title: str = Field(min_length=1, max_length=160)
    explanation: str = Field(min_length=1, max_length=2_000)
    style: Literal["textbook", "blueprint", "minimal", "chalk"] = "textbook"
    html: HtmlPayload | None = None
    graph: GraphPayload | None = None
    formula: FormulaPayload | None = None
    evidence: list[str] = Field(default_factory=list, max_length=20)
    engine: str
    tool: str
    verification: Verification
    timings_ms: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self):
        payloads = {
            "html": self.html,
            "graph": self.graph,
            "formula": self.formula,
        }
        if payloads[self.artifact_type] is None:
            raise ValueError(f"缺少 {self.artifact_type} 产物内容")
        if self.graph:
            node_ids = {node.id for node in self.graph.nodes}
            if len(node_ids) != len(self.graph.nodes):
                raise ValueError("节点 id 不能重复")
            if any(edge.source not in node_ids or edge.target not in node_ids for edge in self.graph.edges):
                raise ValueError("边引用了不存在的节点")
        return self
