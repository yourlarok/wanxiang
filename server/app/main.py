from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from .artifacts import Artifact, VisualizationRequest
from .runtime import RuntimeErrorBase, VisualRuntime

app = FastAPI(title="万相 Wanxiang", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
runtime = VisualRuntime()


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


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
