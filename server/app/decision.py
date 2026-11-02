import json
import os
import time
from dataclasses import dataclass
from typing import Literal

import httpx

from .artifacts import Artifact, VisualizationRequest


@dataclass
class Decision:
    action: Literal["accept", "escalate"]
    confidence: float
    reason: str
    elapsed_ms: float


class JevEngine:
    def __init__(self):
        self.enabled = os.getenv("VIS_JEV_ENABLED", "false").lower() == "true"
        self.base_url = os.getenv("VIS_JEV_BASE_URL", os.getenv("VIS_AGENT_BASE_URL", "")).rstrip("/")
        self.api_key = os.getenv("VIS_JEV_API_KEY", os.getenv("VIS_AGENT_API_KEY", ""))
        self.model = os.getenv("VIS_JEV_MODEL", os.getenv("VIS_AGENT_MODEL", ""))
        self.threshold = float(os.getenv("VIS_JEV_THRESHOLD", "0.72"))

    def should_review(self, artifact: Artifact) -> bool:
        if not self.enabled:
            return False
        if os.getenv("VIS_JEV_REVIEW_MODE", "uncertain") == "always":
            return True
        return artifact.tool == "create_html_artifact" or not artifact.evidence or not artifact.verification.passed

    async def review(self, request: VisualizationRequest, artifact: Artifact) -> Decision:
        if not self.enabled:
            return Decision("accept", 1.0, "确定性校验通过，无需额外评审", 0.0)
        started = time.perf_counter()
        payload = {
            "model": self.model,
            "reasoning_effort": "low",
            "max_completion_tokens": 300,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": '你是高速判别器，不做生成。只输出 {"label":"accept|escalate","confidence":0到1,"reason":"短原因"}。判断视觉产物是否直接回答用户问题、类型是否恰当、是否应升级强模型。确定性校验已通过时不要无故升级。',
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "question": request.text or "图片输入",
                        "artifact_type": artifact.artifact_type,
                        "title": artifact.title,
                        "explanation": artifact.explanation,
                        "tool": artifact.tool,
                        "checks": artifact.verification.checks,
                    }, ensure_ascii=False),
                },
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]["content"]
            data = json.loads(message)
            confidence = max(0.0, min(1.0, float(data["confidence"])))
            action = "accept" if data["label"] == "accept" and confidence >= self.threshold else "escalate"
            return Decision(action, confidence, str(data.get("reason", "")), (time.perf_counter() - started) * 1000)
        except (httpx.HTTPError, KeyError, ValueError, TypeError, json.JSONDecodeError):
            return Decision("accept", 0.0, "JEV 不可用，使用确定性校验结果", (time.perf_counter() - started) * 1000)
