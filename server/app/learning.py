from .artifacts import Artifact, LearningRequest, LearningResponse, OverlayLayout


def learning_response(request: LearningRequest, artifact: Artifact) -> LearningResponse:
    if not request.selection:
        return LearningResponse(artifact=artifact, overlay=OverlayLayout(x=80, y=80, width=760, height=560))
    region = request.selection
    preferred = {
        "create_plot_artifact": (780, 570),
        "create_scene_artifact": (700, 520),
        "create_graph_artifact": (680, 500),
        "create_formula_artifact": (560, 330),
        "create_html_artifact": (740, 560),
    }
    preferred_width, preferred_height = preferred.get(artifact.tool, (700, 520))
    if len(artifact.explanation) > 280:
        preferred_height += 70
    if len(artifact.explanation) > 700:
        preferred_height += 70
    max_width = max(280, int(region.screen_width * 0.92))
    max_height = max(220, int(region.screen_height * 0.9))
    width = min(max(region.width, preferred_width, 360), max_width)
    height = min(max(region.height, preferred_height, 260), max_height)
    center_x = region.x + region.width / 2
    center_y = region.y + region.height / 2
    screen_x = region.screen_x
    screen_y = region.screen_y
    x = round(center_x - width / 2)
    y = round(center_y - height / 2)
    x = min(max(x, screen_x + 12), screen_x + region.screen_width - width - 12)
    y = min(max(y, screen_y + 12), screen_y + region.screen_height - height - 12)
    return LearningResponse(
        artifact=artifact,
        overlay=OverlayLayout(x=x, y=y, width=width, height=height),
    )
