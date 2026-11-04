import hashlib
import json
import os
import time
from html import escape
from typing import Any

import httpx

from .artifacts import Artifact, HtmlPayload, LearningRequest, Verification, VisualizationRequest
from .decision import JevEngine
from .tools import ToolRegistry
from .verifier import verify_artifact


SYSTEM_PROMPT = """
你是开放式可视化 Agent，不是场景分类器。你的任务是直接帮助用户理解问题。
优先创建能直观解释的微场景、模拟、几何图、函数图或交互实验；只有真正的关系或流程才用关系图。
数据、函数、空间结构和三维内容优先调用 create_plot_artifact，用声明式 PlotSpec 交给专业渲染器，不手写绘图代码。
必须调用一个 create_*_artifact 工具完成产物，不要只输出文字回答。
可先调用 get_style_guide 或外部 MCP 工具获取设计/计算能力，再创建产物。
create_html_artifact 支持任意内联 HTML、SVG、CSS 和本地 JavaScript，因此未知领域也应自然生成，不得退回概念分类。
HTML 不引用外部库、图片或字体，不使用 script/iframe/事件属性；JavaScript 只操作本地 SVG/Canvas/DOM，不访问网络、存储或宿主页面。
图形要直接回答用户疑问，文字简明，避免把段落塞进节点。evidence 只记录原文依据，不编造事实。
""".strip()

FAST_SYSTEM_PROMPT = """
你是快速可视化规划器。只进行一次工具调用，不查询风格或外部工具，不解释工具过程。
数据、函数、几何、矩阵、张量、空间结构优先 create_plot_artifact，以紧凑声明式 PlotSpec 描述数据、视觉编码和多子图布局，由本地 Matplotlib 专业渲染。
规则三维网格用 voxels：shape 给三个维度，coordinates 只给非默认单元，colors 配合 color_by 表达维度差异；不要逐图元摆平面矩形。
简单自定义示意才用 create_scene_artifact；真正的实体关系或流程用 create_graph_artifact；纯公式解释用 create_formula_artifact。
同一问题的对比子图必须保持一致的图形类型、视角和视觉编码；3–4 个面板默认使用 2×2 均衡布局，不要横向挤成一排。
颜色优先使用 accent、highlight、ink、muted 等语义色，使用户选择的主题统一生效。
标签简短且准确，只输出回答问题所需的数据与视觉结构。
""".strip()

LEARNING_SYSTEM_PROMPT = """
这是陪伴学习场景。第一张图片是用户框选的重点，第二张图片（若有）是此前常态读取的框外静态快照。
先理解框内内容，再判断它是否依赖框外定义、前文、图表或题目条件；只在确有需要时结合背景，不引入无关内容。
每次创建产物都必须填写 context_used 和 context_reason：明确是否真正使用了框外上下文以及简短原因。
解释应帮助用户继续学习：先解除当前疑惑，再给一个贴切例子或必要下一步，避免泛泛总结整张屏幕。
""".strip()


class RuntimeErrorBase(RuntimeError):
    pass


class VisualRuntime:
    def __init__(self):
        self.base_url = os.getenv("VIS_AGENT_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("VIS_AGENT_API_KEY", "")
        self.model = os.getenv("VIS_AGENT_MODEL", "")
        self.reasoning_effort = os.getenv("VIS_AGENT_REASONING_EFFORT", "low")
        self.planner_reasoning_effort = os.getenv("VIS_PLANNER_REASONING_EFFORT", "low")
        self.fast_mode = os.getenv("VIS_FAST_MODE", "true").lower() != "false"
        self.registry = ToolRegistry(f"model:{self.model}" if self.model else "local-open-html")
        self.jev = JevEngine()
        self.cache: dict[str, Artifact] = {}

    @property
    def mode(self) -> str:
        return "model" if self.base_url and self.api_key and self.model else "local"

    async def generate(self, request: VisualizationRequest) -> Artifact:
        key = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        if key in self.cache:
            return self.cache[key].model_copy(deep=True)
        if self.mode == "local":
            artifact = self._local_artifact(request)
        else:
            artifact = await self._model_artifact(request)
            if self.fast_mode and self.jev.should_review(artifact):
                decision = await self.jev.review(request, artifact)
                artifact.verification.checks.append(
                    f"JEV {decision.action}，置信度 {decision.confidence:.2f}，{decision.elapsed_ms:.0f}ms"
                )
                if decision.action == "escalate":
                    self.fast_mode = False
                    try:
                        artifact = await self._model_artifact(request)
                        artifact.verification.checks.append("低置信结果已升级至完整 Agent")
                    finally:
                        self.fast_mode = True
        if len(self.cache) >= 64:
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = artifact
        return artifact.model_copy(deep=True)

    def _local_artifact(self, request: VisualizationRequest) -> Artifact:
        if not request.text:
            raise RuntimeErrorBase("截图识别需要配置多模态模型")
        artifact = Artifact(
            artifact_type="html",
            title="开放内容视图",
            explanation="当前未配置模型，先展示原始内容；配置多模态模型后可自动生成教学微场景。",
            style=request.style,
            html=HtmlPayload(
                body=f'<section class="card"><h2>原始内容</h2><p>{escape(request.text)}</p></section>',
                css="h2{font-size:18px}p{color:var(--muted);white-space:pre-wrap}",
                javascript="",
            ),
            evidence=[request.text[:200]],
            engine="local-open-html",
            tool="local_fallback",
            verification=Verification(passed=False),
        )
        return verify_artifact(artifact)

    async def _model_artifact(self, request: VisualizationRequest) -> Artifact:
        started = time.perf_counter()
        model_ms = 0.0
        learning = isinstance(request, LearningRequest)
        content: list[dict[str, Any]] = [{
            "type": "text",
            "text": f"表达偏好：{request.preference}\n视觉风格：{request.style}\n用户内容：{request.text or '识别框选截图并选择最有助于理解的视觉表达'}",
        }]

        def append_image(target: list[dict[str, Any]], value: str) -> None:
            image = value if value.startswith("data:image/") else f"data:image/png;base64,{value}"
            target.append({"type": "image_url", "image_url": {"url": image}})

        if request.image_base64:
            append_image(content, request.image_base64)
        if learning and request.context_mode != "never":
            if request.context_text:
                content.append({"type": "text", "text": f"可选框外文字上下文：\n{request.context_text}"})
            if request.context_image_base64:
                content.append({"type": "text", "text": "以下是框外静态快照，仅在当前疑惑需要时参考："})
                append_image(content, request.context_image_base64)
        system_prompt = FAST_SYSTEM_PROMPT if self.fast_mode else SYSTEM_PROMPT
        if learning:
            system_prompt = f"{LEARNING_SYSTEM_PROMPT}\n{system_prompt}"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]
        tools = self.registry.builtin_tools() if self.fast_mode else await self.registry.tools()
        if self.fast_mode:
            tools = [
                tool for tool in tools
                if tool["function"]["name"] in {"create_plot_artifact", "create_scene_artifact", "create_graph_artifact", "create_formula_artifact"}
            ]
        if learning:
            for tool in tools:
                parameters = tool["function"]["parameters"]
                parameters["properties"]["context_used"] = {"type": "boolean", "description": "是否真正使用了框外上下文"}
                parameters["properties"]["context_reason"] = {"type": "string", "description": "上下文判断的简短原因"}
                parameters["required"] = [*parameters["required"], "context_used", "context_reason"]

        async with httpx.AsyncClient(timeout=120) as client:
            for _ in range(5):
                payload: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "max_completion_tokens": 2500 if self.fast_mode else 7000,
                    "reasoning_effort": self.planner_reasoning_effort if self.fast_mode else self.reasoning_effort,
                }
                model_started = time.perf_counter()
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                model_ms += (time.perf_counter() - model_started) * 1000
                if response.is_error:
                    raise RuntimeErrorBase(f"模型服务返回 HTTP {response.status_code}")
                data = response.json()
                message = data["choices"][0]["message"]
                messages.append(message)
                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    messages.append({"role": "user", "content": "请使用 create_*_artifact 工具完成视觉产物，不要只解释。"})
                    continue

                for call in tool_calls:
                    function = call["function"]
                    try:
                        arguments = json.loads(function.get("arguments") or "{}")
                        result = await self.registry.call(function["name"], arguments)
                        if result.artifact:
                            result.artifact.timings_ms["model"] = model_ms
                            result.artifact.timings_ms["total"] = (time.perf_counter() - started) * 1000
                            if learning:
                                result.artifact.context_used = arguments.get("context_used")
                                result.artifact.context_reason = arguments.get("context_reason", "")
                            return result.artifact
                        tool_content = result.content
                    except (ValueError, KeyError, TypeError) as error:
                        tool_content = f"工具调用或校验失败：{error}。请修正后重试。"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": function["name"],
                        "content": tool_content,
                    })
        raise RuntimeErrorBase("Agent 未能在限定步骤内生成合法视觉产物")
