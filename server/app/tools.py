import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .artifacts import Artifact, FormulaPayload, GraphPayload, HtmlPayload, Verification
from .scene import SceneSpec, render_scene
from .styles import style_guide
from .verifier import verify_artifact


@dataclass
class ToolResult:
    content: str
    artifact: Artifact | None = None


def openai_tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
        },
    }


COMMON = {
    "title": {"type": "string", "description": "不超过30字的标题"},
    "explanation": {"type": "string", "description": "简明扼要、直接帮助理解的解释"},
    "style": {"type": "string", "enum": ["textbook", "blueprint", "minimal", "chalk"]},
    "evidence": {"type": "array", "items": {"type": "string"}, "description": "与原文对应的依据"},
}


class ToolRegistry:
    def __init__(self, engine: str):
        self.engine = engine
        self.external_tools: dict[str, dict[str, Any]] = {}
        self.external_openai_tools: list[dict[str, Any]] = []
        self.discovered_at = 0.0
        self.servers = self._server_config()

    def _server_config(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(os.getenv("VIS_MCP_SERVERS", "[]"))
            return value if isinstance(value, list) else []
        except json.JSONDecodeError:
            return []

    def builtin_tools(self) -> list[dict[str, Any]]:
        scene_schema = SceneSpec.model_json_schema()
        scene_schema["properties"]["elements"]["items"] = scene_schema["$defs"].pop("SceneElement")
        scene_schema.pop("$defs")
        return [
            openai_tool(
                "create_scene_artifact",
                "以紧凑场景元素计划快速生成 SVG。模型只需给出文字、矩形、网格、圆、线和箭头及坐标，本地完成渲染。适合教学示意、结构嵌套、几何、流程直觉和函数草图。",
                {**COMMON, "scene": scene_schema},
                ["title", "explanation", "style", "scene", "evidence"],
            ),
            openai_tool(
                "get_style_guide",
                "按视觉风格获取设计令牌和表达指南。需要创建视觉产物时可按需调用。",
                {"style": COMMON["style"]},
                ["style"],
            ),
            openai_tool(
                "create_html_artifact",
                "创建开放式教学微场景、SVG插图、几何模拟或交互实验。适合无法由普通关系图表达的概念。HTML body 不得包含 script、iframe、外部资源或事件属性；JavaScript 仅用于本地交互。",
                {
                    **COMMON,
                    "body": {"type": "string", "description": "内联HTML或SVG body"},
                    "css": {"type": "string", "description": "局部CSS，不使用url或@import"},
                    "javascript": {"type": "string", "description": "可选的本地交互JavaScript，不访问网络、存储或宿主页面"},
                },
                ["title", "explanation", "style", "body", "css", "javascript", "evidence"],
            ),
            openai_tool(
                "create_graph_artifact",
                "仅当内容确实是实体关系、因果结构、流程或步骤时，创建专业关系图。",
                {
                    **COMMON,
                    "kind": {"type": "string", "enum": ["concept", "process"]},
                    "nodes": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "label": {"type": "string"}, "description": {"type": "string"}}, "required": ["id", "label", "description"], "additionalProperties": False}},
                    "edges": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "target": {"type": "string"}, "label": {"type": "string"}}, "required": ["source", "target", "label"], "additionalProperties": False}},
                },
                ["title", "explanation", "style", "kind", "nodes", "edges", "evidence"],
            ),
            openai_tool(
                "create_formula_artifact",
                "创建 KaTeX 公式及变量解释；若需要函数图像或几何直觉，应改用 create_html_artifact。",
                {
                    **COMMON,
                    "latex": {"type": "string"},
                    "variables": {"type": "array", "items": {"type": "object", "properties": {"symbol": {"type": "string"}, "meaning": {"type": "string"}}, "required": ["symbol", "meaning"], "additionalProperties": False}},
                },
                ["title", "explanation", "style", "latex", "variables", "evidence"],
            ),
        ]

    async def tools(self) -> list[dict[str, Any]]:
        if self.servers and time.monotonic() - self.discovered_at > 60:
            await self._discover_external()
        return [*self.builtin_tools(), *self.external_openai_tools]

    async def _discover_external(self) -> None:
        self.external_tools.clear()
        self.external_openai_tools.clear()
        for server in self.servers:
            name = re.sub(r"[^a-zA-Z0-9_]", "_", str(server.get("name", "mcp")))
            try:
                params = StdioServerParameters(command=server["command"], args=server.get("args", []))
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        with anyio.fail_after(8):
                            await session.initialize()
                            response = await session.list_tools()
                        for tool in response.tools:
                            external_name = f"mcp__{name}__{tool.name}"
                            self.external_tools[external_name] = {"server": server, "name": tool.name}
                            self.external_openai_tools.append({
                                "type": "function",
                                "function": {
                                    "name": external_name,
                                    "description": tool.description or f"调用 {name} 的 {tool.name}",
                                    "parameters": tool.inputSchema,
                                },
                            })
            except (OSError, KeyError, TimeoutError, RuntimeError):
                continue
        self.discovered_at = time.monotonic()

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name == "create_scene_artifact":
            scene = SceneSpec.model_validate(arguments["scene"])
            artifact = Artifact(
                artifact_type="html",
                title=arguments["title"],
                explanation=arguments["explanation"],
                style=arguments["style"],
                html=HtmlPayload(body=render_scene(scene), css=".scene{display:block;width:100%;height:auto}", javascript=""),
                evidence=arguments.get("evidence", []),
                engine=self.engine,
                tool=name,
                verification=Verification(passed=False),
            )
            return ToolResult("紧凑场景已渲染为 SVG 并通过校验", verify_artifact(artifact))
        if name == "get_style_guide":
            return ToolResult(json.dumps(style_guide(arguments["style"]), ensure_ascii=False))
        if name == "create_html_artifact":
            artifact = Artifact(
                artifact_type="html",
                title=arguments["title"],
                explanation=arguments["explanation"],
                style=arguments["style"],
                html=HtmlPayload(body=arguments["body"], css=arguments["css"], javascript=arguments["javascript"]),
                evidence=arguments.get("evidence", []),
                engine=self.engine,
                tool=name,
                verification=Verification(passed=False),
            )
            return ToolResult("开放 HTML 产物已创建并通过校验", verify_artifact(artifact))
        if name == "create_graph_artifact":
            artifact = Artifact(
                artifact_type="graph",
                title=arguments["title"],
                explanation=arguments["explanation"],
                style=arguments["style"],
                graph=GraphPayload.model_validate({"kind": arguments["kind"], "nodes": arguments["nodes"], "edges": arguments["edges"]}),
                evidence=arguments.get("evidence", []),
                engine=self.engine,
                tool=name,
                verification=Verification(passed=False),
            )
            return ToolResult("关系图产物已创建并通过校验", verify_artifact(artifact))
        if name == "create_formula_artifact":
            artifact = Artifact(
                artifact_type="formula",
                title=arguments["title"],
                explanation=arguments["explanation"],
                style=arguments["style"],
                formula=FormulaPayload.model_validate({"latex": arguments["latex"], "variables": arguments["variables"]}),
                evidence=arguments.get("evidence", []),
                engine=self.engine,
                tool=name,
                verification=Verification(passed=False),
            )
            return ToolResult("公式产物已创建并通过校验", verify_artifact(artifact))
        if name in self.external_tools:
            return ToolResult(await self._call_external(name, arguments))
        raise ValueError(f"未知工具：{name}")

    async def _call_external(self, name: str, arguments: dict[str, Any]) -> str:
        target = self.external_tools[name]
        server = target["server"]
        params = StdioServerParameters(command=server["command"], args=server.get("args", []))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                with anyio.fail_after(30):
                    await session.initialize()
                    result = await session.call_tool(target["name"], arguments)
                content = []
                for item in result.content:
                    content.append(item.text if hasattr(item, "text") else json.dumps(item.model_dump(), default=str))
                return "\n".join(content)[:100_000]
