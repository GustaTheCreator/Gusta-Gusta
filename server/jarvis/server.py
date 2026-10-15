"""Servidor web: entrega a página e liga o browser ao bot por WebRTC."""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from .bot import run_bot
from .config import settings
from .stt import get_model

webrtc = SmallWebRTCRequestHandler()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Carrega o Whisper no arranque para a primeira pergunta não esperar por ele.
    get_model(settings.whisper_model)
    logger.info("Whisper pronto")
    yield
    await webrtc.close()


app = FastAPI(title="Jarvis", lifespan=lifespan)


@app.post("/api/offer")
async def offer(request: SmallWebRTCRequest, background_tasks: BackgroundTasks):
    async def on_connection(connection: SmallWebRTCConnection):
        background_tasks.add_task(run_bot, connection)

    return await webrtc.handle_web_request(request=request, webrtc_connection_callback=on_connection)


@app.patch("/api/offer")
async def ice_candidate(request: SmallWebRTCPatchRequest):
    await webrtc.handle_patch_request(request)
    return {"status": "success"}


@app.get("/api/health")
async def health():
    return {"ok": True}


if settings.web_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.web_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = (settings.web_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(settings.web_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(settings.web_dir / "index.html")


def main():
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
