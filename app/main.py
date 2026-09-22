"""FastAPI app: upload a GPX route, get a head/tail/crosswind analysis for it."""

import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from analyzer import analyze_segments
from gpx_parser import parse_gpx, reverse_route

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.environ.get("GPX_UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="GPX Wind Analyzer")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/health")
async def health():
    return {"status": "ok"}


def _parse_ride_datetime(date_str: str, time_str: str) -> datetime:
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError("Ongeldige datum of tijd. Verwacht formaat: JJJJ-MM-DD en UU:MM.") from exc


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    date: str = Form(...),
    time: str = Form(...),
    direction: str = Form("normal"),
):
    gpx_path = UPLOAD_DIR / f"{uuid.uuid4()}.gpx"

    try:
        ride_dt = _parse_ride_datetime(date, time)

        with gpx_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info("GPX opgeslagen: %s", gpx_path)

        route = parse_gpx(gpx_path)
        logger.info("GPX punten: %d, segmenten: %d", len(route["points"]), len(route["segments"]))

        if direction == "reverse":
            logger.info("Route wordt omgekeerd")
            route = reverse_route(route)

        wind_data = await analyze_segments(route["segments"], ride_dt)

        return JSONResponse(
            {
                "route": {
                    "points": route["points"],
                    "distance_km": route["distance_km"],
                    "coordinates": route["coordinates"],
                },
                "wind": wind_data,
            }
        )

    except ValueError as exc:
        logger.warning("Ongeldige invoer: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except httpx.HTTPError as exc:
        logger.error("Weerservice niet bereikbaar: %s", exc)
        raise HTTPException(status_code=502, detail="Weerservice tijdelijk niet bereikbaar.") from exc

    except Exception as exc:
        logger.exception("Onverwachte fout bij analyse")
        raise HTTPException(status_code=500, detail="Onverwachte fout bij analyse.") from exc
