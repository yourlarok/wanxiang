from mcp.server.fastmcp import FastMCP

from .artifacts import VisualizationRequest
from .runtime import VisualRuntime
from .styles import STYLE_GUIDES

runtime = VisualRuntime()
mcp = FastMCP("万相 Wanxiang")


@mcp.tool()
async def visualize(
    text: str | None = None,
    image_base64: str | None = None,
    preference: str = "auto",
    style: str = "textbook",
) -> dict:
    """理解文本或截图，生成开放 HTML/SVG、关系图或公式视觉产物。优先用于需要直观解释、模拟、几何图和交互实验的任务。"""
    request = VisualizationRequest(
        text=text,
        image_base64=image_base64,
        preference=preference,
        style=style,
    )
    artifact = await runtime.generate(request)
    return artifact.model_dump(mode="json")


@mcp.tool()
def list_visual_styles() -> dict:
    """列出万相支持的视觉风格及其设计令牌。"""
    return STYLE_GUIDES


if __name__ == "__main__":
    mcp.run(transport="stdio")
