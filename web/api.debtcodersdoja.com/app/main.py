"""FastAPI service for api.debtcodersdoja.com."""
from __future__ import annotations

import os
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("API_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.getenv("API_UPLOAD_DIR", BASE_DIR / "uploads"))
MOTD_PATH = Path(os.getenv("API_MOTD_PATH", DATA_DIR / "MOTD.md"))
PUBLIC_SERVER_URL = os.getenv("API_PUBLIC_URL", "https://api.debtcodersdoja.com")
SERVICE_VERSION = os.getenv("API_VERSION", "0.1.0")
DUCKDUCKGO_ENDPOINT = "https://api.duckduckgo.com/"

START_TIME = time.time()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
  title="Debt Coders Doja API",
  description=textwrap.dedent(
    """
    API surface for the Debt Coders Doja GPT integration. Provides a MOTD feed, live diagnostics, and a DuckDuckGo proxy.
    """
  ).strip(),
  version=SERVICE_VERSION,
  docs_url="/docs",
  redoc_url="/redoc",
  openapi_url="/openapi.json",
  openapi_version="3.1.0",
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


class HealthResponse(BaseModel):
  status: str = Field(default="ok", description="High-level service status indicator")
  uptime_seconds: float = Field(description="Seconds since the process started")


class DiagnosticsResponse(BaseModel):
  status: str
  version: str
  uptime_seconds: float
  motd_exists: bool
  motd_last_modified: datetime | None
  upload_dir: str
  upload_file_count: int
  upload_disk_usage_bytes: int
  duckduckgo_ready: bool
  python_version: str


class DuckDuckGoResult(BaseModel):
  title: str | None = Field(default=None, description="Result title from DuckDuckGo")
  url: str | None = Field(default=None, description="Canonical URL for the result")
  summary: str | None = Field(default=None, description="Plain text summary snippet")


class DuckDuckGoResponse(BaseModel):
  query: str
  abstract: str | None
  answer: str | None
  results: List[DuckDuckGoResult]
  raw: Dict[str, Any] = Field(default_factory=dict, description="Raw DuckDuckGo payload (redacted keys removed)")


class UploadSummary(BaseModel):
  filename: str
  bytes_written: int


class UploadListingItem(BaseModel):
  filename: str
  size_bytes: int
  modified_at: datetime


class UploadListingResponse(BaseModel):
  files: List[UploadListingItem]


def sanitize_filename(filename: str) -> str:
  keep = (char for char in filename if char.isalnum() or char in {"-", "_", "."})
  cleaned = "".join(keep).lstrip(".")
  if not cleaned:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"upload-{timestamp}"
  return cleaned[:200]


def duckduckgo_payload_filter(payload: Dict[str, Any]) -> Dict[str, Any]:
  allowed_keys = {
    "Abstract",
    "Answer",
    "RelatedTopics",
    "Results",
  }
  return {key: payload[key] for key in allowed_keys if key in payload}


def ensure_motd_path() -> Path:
  if MOTD_PATH.exists():
    return MOTD_PATH
  MOTD_PATH.write_text("MOTD not set. Edit MOTD.md to update.\n", encoding="utf-8")
  return MOTD_PATH


def service_uptime() -> float:
  return round(time.time() - START_TIME, 3)


def custom_openapi() -> Dict[str, Any]:
  if app.openapi_schema:
    return app.openapi_schema
  openapi_schema = get_openapi(
    title=app.title,
    version=app.version,
    routes=app.routes,
    description=app.description,
  )
  openapi_schema["servers"] = [{"url": PUBLIC_SERVER_URL}]
  app.openapi_schema = openapi_schema
  return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[assignment]


async def fetch_duckduckgo(query: str) -> DuckDuckGoResponse:
  params = {
    "q": query,
    "format": "json",
    "no_redirect": "1",
    "no_html": "1",
  }
  async with httpx.AsyncClient(timeout=10) as client:
    response = await client.get(DUCKDUCKGO_ENDPOINT, params=params)
  try:
    response.raise_for_status()
  except httpx.HTTPStatusError as exc:
    raise HTTPException(status_code=exc.response.status_code, detail="DuckDuckGo query failed") from exc
  payload = response.json()
  focus_keys = duckduckgo_payload_filter(payload)

  results: List[DuckDuckGoResult] = []
  for item in payload.get("Results", []):
    results.append(
      DuckDuckGoResult(
        title=item.get("Text"),
        url=item.get("FirstURL"),
        summary=item.get("Text"),
      )
    )

  if not results and payload.get("RelatedTopics"):
    for topic in payload["RelatedTopics"]:
      if isinstance(topic, dict) and topic.get("Text"):
        results.append(
          DuckDuckGoResult(
            title=topic.get("Text"),
            url=topic.get("FirstURL"),
            summary=topic.get("Text"),
          )
        )

  return DuckDuckGoResponse(
    query=query,
    abstract=payload.get("Abstract"),
    answer=payload.get("Answer"),
    results=results,
    raw=focus_keys,
  )


def list_uploads() -> List[UploadListingItem]:
  items: List[UploadListingItem] = []
  for entry in sorted(UPLOAD_DIR.iterdir()):
    if not entry.is_file():
      continue
    stat = entry.stat()
    items.append(
      UploadListingItem(
        filename=entry.name,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
      )
    )
  return items


def motd_dependency() -> Path:
  path = ensure_motd_path()
  if not path.exists():
    raise HTTPException(status_code=500, detail="MOTD file missing")
  return path


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
  return RedirectResponse(url="/docs", status_code=302)


@app.get("/healthz", response_model=HealthResponse, tags=["system"])
async def healthcheck() -> HealthResponse:
  return HealthResponse(status="ok", uptime_seconds=service_uptime())


@app.get("/diagnostics", response_model=DiagnosticsResponse, tags=["system"])
async def diagnostics() -> DiagnosticsResponse:
  uptime = service_uptime()
  python_version = f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
  motd_path = ensure_motd_path()
  motd_stat = motd_path.stat() if motd_path.exists() else None
  duckduckgo_ready = False
  try:
    async with httpx.AsyncClient(timeout=2) as client:
      resp = await client.get("https://api.duckduckgo.com/", params={"q": "ping", "format": "json"})
      duckduckgo_ready = resp.status_code == 200
  except httpx.HTTPError:
    duckduckgo_ready = False

  items = list_uploads() if UPLOAD_DIR.exists() else []
  file_count = len(items)
  usage_bytes = sum(item.size_bytes for item in items)

  return DiagnosticsResponse(
    status="ok" if duckduckgo_ready else "degraded",
    version=SERVICE_VERSION,
    uptime_seconds=uptime,
    motd_exists=motd_path.exists(),
    motd_last_modified=datetime.fromtimestamp(motd_stat.st_mtime, tz=timezone.utc) if motd_stat else None,
    upload_dir=str(UPLOAD_DIR),
    upload_file_count=file_count,
    upload_disk_usage_bytes=usage_bytes,
    duckduckgo_ready=duckduckgo_ready,
    python_version=python_version,
  )


@app.get("/motd", response_class=PlainTextResponse, tags=["content"])
async def motd(path: Path = Depends(motd_dependency)) -> PlainTextResponse:
  try:
    content = path.read_text(encoding="utf-8")
  except OSError as exc:
    raise HTTPException(status_code=500, detail=f"Failed to read MOTD: {exc}") from exc
  return PlainTextResponse(content)


@app.get("/duckduckgo", response_model=DuckDuckGoResponse, tags=["search"])
async def duckduckgo(query: str = Query(..., alias="q", description="Search terms to send to DuckDuckGo")) -> DuckDuckGoResponse:
  if not query.strip():
    raise HTTPException(status_code=400, detail="Query must not be empty")
  return await fetch_duckduckgo(query.strip())


@app.post("/upload", response_model=List[UploadSummary], tags=["uploads"])
async def upload(files: List[UploadFile] = File(...)) -> List[UploadSummary]:
  if not files:
    raise HTTPException(status_code=400, detail="At least one file is required")

  saved: List[UploadSummary] = []
  for upload_file in files:
    sanitized = sanitize_filename(upload_file.filename or "")
    destination = UPLOAD_DIR / sanitized
    counter = 1
    while destination.exists():
      stem = destination.stem
      suffix = destination.suffix
      destination = UPLOAD_DIR / f"{stem}-{counter}{suffix}"
      counter += 1

    try:
      content = await upload_file.read()
      destination.write_bytes(content)
    except OSError as exc:
      raise HTTPException(status_code=500, detail=f"Failed to write file {sanitized}: {exc}") from exc
    finally:
      await upload_file.close()

    saved.append(UploadSummary(filename=destination.name, bytes_written=len(content)))

  return saved


@app.get("/uploads", response_model=UploadListingResponse, tags=["uploads"])
async def uploads_list() -> UploadListingResponse:
  items = list_uploads()
  return UploadListingResponse(files=items)


@app.get("/upload/{filename:path}", response_class=FileResponse, tags=["uploads"])
async def upload_fetch(filename: str) -> FileResponse:
  sanitized = sanitize_filename(filename)
  file_path = UPLOAD_DIR / sanitized
  if not file_path.exists() or not file_path.is_file():
    raise HTTPException(status_code=404, detail="File not found")
  return FileResponse(file_path)


@app.delete("/upload/{filename:path}", response_model=UploadSummary, tags=["uploads"])
async def upload_delete(filename: str) -> UploadSummary:
  sanitized = sanitize_filename(filename)
  file_path = UPLOAD_DIR / sanitized
  if not file_path.exists() or not file_path.is_file():
    raise HTTPException(status_code=404, detail="File not found")
  size = file_path.stat().st_size
  try:
    file_path.unlink()
  except OSError as exc:
    raise HTTPException(status_code=500, detail=f"Failed to delete file {sanitized}: {exc}") from exc
  return UploadSummary(filename=sanitized, bytes_written=size)


@app.exception_handler(httpx.HTTPError)
async def httpx_error_handler(_: Any, exc: httpx.HTTPError) -> JSONResponse:
  return JSONResponse(status_code=502, content={"detail": f"External request failed: {exc}"})
