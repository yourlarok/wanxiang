import logging
import time
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from .artifacts import Artifact, LearningRequest, LearningResponse, VisualizationRequest
from .learning import learning_response
from .preview import PREVIEW_HTML
from .runtime import RuntimeErrorBase, VisualRuntime

app = FastAPI(title="万相 Wanxiang", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
runtime = VisualRuntime()
logger = logging.getLogger("wanxiang")


@app.middleware("http")
async def measure_duration(request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.0f}"
    logger.info("%s %s completed in %.2fs", request.method, request.url.path, elapsed_ms / 1000)
    return response


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/preview", response_class=HTMLResponse, include_in_schema=False)
def preview():
    return PREVIEW_HTML


@app.get("/health")
def health():
    return {"status": "ok", "agent_mode": runtime.mode, "protocol": "artifact-2.0"}


@app.post("/v2/visualizations", response_model=Artifact)
async def visualize(request: VisualizationRequest):
    try:
        return await runtime.generate(request)
    except RuntimeErrorBase as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except (httpx.HTTPError, ValidationError, ValueError) as error:
        raise HTTPException(status_code=502, detail="可视化服务暂时不可用") from error


@app.post("/v2/learning", response_model=LearningResponse)
async def learn(request: LearningRequest):
    try:
        artifact = await runtime.generate(request)
        return learning_response(request, artifact)
    except RuntimeErrorBase as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except (httpx.HTTPError, ValidationError, ValueError) as error:
        raise HTTPException(status_code=502, detail="陪伴学习服务暂时不可用") from error


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
