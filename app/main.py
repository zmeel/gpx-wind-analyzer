"""FastAPI app: upload one or two GPX routes, get a head/tail/crosswind analysis for each."""

import asyncio
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

STATIC_DIR = Path("static")

app = FastAPI(title="GPX Wind Analyzer")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _asset_version() -> str:
    """Cache-busting token for style.css/app.js, so browsers fetch the new
    versions right after a deploy instead of serving a stale cached copy
    from the same URL."""
    try:
        newest_mtime = max(
            (STATIC_DIR / "app.js").stat().st_mtime,
            (STATIC_DIR / "style.css").stat().st_mtime,
        )
        return str(int(newest_mtime))
    except OSError:
        return "0"


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"asset_version": _asset_version()},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


def _parse_ride_datetime(date_str: str, time_str: str) -> datetime:
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError("Ongeldige datum of tijd. Verwacht formaat: JJJJ-MM-DD en UU:MM.") from exc


async def _analyze_route(file: UploadFile, direction: str, ride_dt: datetime, label: str) -> dict:
    gpx_path = UPLOAD_DIR / f"{uuid.uuid4()}.gpx"

    with gpx_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    logger.info("GPX opgeslagen (%s): %s", label, gpx_path)

    route = parse_gpx(gpx_path)
    logger.info("%s: %d punten, %d segmenten", label, len(route["points"]), len(route["segments"]))

    if direction == "reverse":
        route = reverse_route(route)

    wind_data = await analyze_segments(route["segments"], ride_dt)

    return {
        "label": label,
        "route": {
            "points": route["points"],
            "distance_km": route["distance_km"],
            "coordinates": route["coordinates"],
        },
        "wind": wind_data,
    }


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    date: str = Form(...),
    time: str = Form(...),
    direction: str = Form("normal"),
    file2: UploadFile | None = File(None),
    direction2: str = Form("normal"),
):
    try:
        ride_dt = _parse_ride_datetime(date, time)

        tasks = [_analyze_route(file, direction, ride_dt, file.filename or "Route 1")]
        if file2 is not None and file2.filename:
            tasks.append(_analyze_route(file2, direction2, ride_dt, file2.filename or "Route 2"))

        routes = await asyncio.gather(*tasks)

        return JSONResponse({"routes": routes})

    except ValueError as exc:
        logger.warning("Ongeldige invoer: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except httpx.HTTPError as exc:
        logger.error("Weerservice niet bereikbaar: %s", exc)
        raise HTTPException(status_code=502, detail="Weerservice tijdelijk niet bereikbaar.") from exc

    except Exception as exc:
        logger.exception("Onverwachte fout bij analyse")
        raise HTTPException(status_code=500, detail="Onverwachte fout bij analyse.") from exc
