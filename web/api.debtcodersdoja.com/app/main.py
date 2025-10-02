"""FastAPI service for api.debtcodersdoja.com."""
from __future__ import annotations

import os
import shlex
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
import markdown

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("API_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.getenv("API_UPLOAD_DIR", BASE_DIR / "uploads"))
MOTD_PATH = Path(os.getenv("API_MOTD_PATH", DATA_DIR / "MOTD.md"))
PUBLIC_SERVER_URL = os.getenv("API_PUBLIC_URL", "https://api.debtcodersdoja.com")
SERVICE_VERSION = os.getenv("API_VERSION", "0.1.0")
DUCKDUCKGO_ENDPOINT = "https://api.duckduckgo.com/"
MAX_TEXT_FILE_BYTES = int(os.getenv("API_TEXT_LIMIT_BYTES", "524288"))  # 512 KiB default
API_ACCESS_KEY = os.getenv("API_ACCESS_KEY")

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


@app.middleware("http")
async def enforce_api_key(request: Request, call_next):
  if API_ACCESS_KEY:
    header_value = request.headers.get("x-doja-key")
    if header_value != API_ACCESS_KEY:
      return JSONResponse(status_code=401, content={"detail": "API key required"})
  return await call_next(request)


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


class TextFilePayload(BaseModel):
  content: str = Field(default="", description="UTF-8 encoded file contents")


class MotdUpdateResponse(BaseModel):
  message: str
  bytes_written: int
  updated_at: datetime


class UploadCommandRequest(BaseModel):
  command: str = Field(description="Terminal-like instruction: ls, cat <file>, rm <file>, touch <file>, mv <src> <dst>")


class UploadCommandResponse(BaseModel):
  command: str
  output: List[str]
  status: str
  error: str | None = None


class RenamePayload(BaseModel):
  target: str = Field(description="Desired new filename for the specified upload")


class FSListItem(BaseModel):
  path: str
  is_dir: bool
  size_bytes: Optional[int]
  modified_at: datetime


class FSListResponse(BaseModel):
  items: List[FSListItem]


class FSWritePayload(BaseModel):
  filename: str = Field(description="Path relative to uploads root")
  content: str = Field(description="File contents to write (UTF-8)")


class FSDeletePayload(BaseModel):
  filename: str = Field(description="Path relative to uploads root")


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


def upload_path_from_name(filename: str) -> Path:
  sanitized = sanitize_filename(filename or "")
  return UPLOAD_DIR / sanitized


def read_text_file(path: Path) -> str:
  if not path.exists() or not path.is_file():
    raise HTTPException(status_code=404, detail="File not found")
  if path.stat().st_size > MAX_TEXT_FILE_BYTES:
    raise HTTPException(status_code=413, detail="File too large to preview")
  try:
    return path.read_text(encoding="utf-8")
  except UnicodeDecodeError as exc:
    raise HTTPException(status_code=415, detail="File is not valid UTF-8") from exc


def write_text_file(path: Path, content: str) -> UploadSummary:
  path.parent.mkdir(parents=True, exist_ok=True)
  encoded = content.encode("utf-8")
  if len(encoded) > MAX_TEXT_FILE_BYTES:
    raise HTTPException(status_code=413, detail="Text payload exceeds size limit")
  try:
    path.write_bytes(encoded)
  except OSError as exc:
    raise HTTPException(status_code=500, detail=f"Failed to write file {path.name}: {exc}") from exc
  return UploadSummary(filename=path.name, bytes_written=len(encoded))


def delete_upload_file(path: Path) -> UploadSummary:
  if not path.exists() or not path.is_file():
    raise HTTPException(status_code=404, detail="File not found")
  size = path.stat().st_size
  try:
    path.unlink()
  except OSError as exc:
    raise HTTPException(status_code=500, detail=f"Failed to delete file {path.name}: {exc}") from exc
  return UploadSummary(filename=path.name, bytes_written=size)


def rename_upload_file(src_name: str, dest_name: str) -> UploadSummary:
  src_path = upload_path_from_name(src_name)
  dest_path = upload_path_from_name(dest_name)
  if not src_path.exists() or not src_path.is_file():
    raise HTTPException(status_code=404, detail="Source file not found")
  if dest_path.exists():
    raise HTTPException(status_code=409, detail="Destination file already exists")
  try:
    src_path.rename(dest_path)
  except OSError as exc:
    raise HTTPException(status_code=500, detail=f"Failed to rename file: {exc}") from exc
  return UploadSummary(filename=dest_path.name, bytes_written=dest_path.stat().st_size)


def run_upload_command(command: str) -> UploadCommandResponse:
  command = command.strip()
  if not command:
    return UploadCommandResponse(command=command, output=[], status="noop", error="No command provided")

  try:
    args = shlex.split(command)
  except ValueError as exc:
    return UploadCommandResponse(command=command, output=[], status="error", error=str(exc))

  if not args:
    return UploadCommandResponse(command=command, output=[], status="noop", error="No command provided")

  cmd, *rest = args
  output: List[str] = []

  try:
    if cmd == "ls":
      items = list_uploads()
      if not items:
        output.append("(empty)")
      else:
        for item in items:
          output.append(f"{item.size_bytes:>8}  {item.modified_at.isoformat()}  {item.filename}")
      status = "ok"
    elif cmd == "cat":
      if not rest:
        raise HTTPException(status_code=400, detail="cat requires a filename")
      content = read_text_file(upload_path_from_name(rest[0]))
      output.extend(content.splitlines() or [""])
      status = "ok"
    elif cmd == "rm":
      if not rest:
        raise HTTPException(status_code=400, detail="rm requires a filename")
      summary = delete_upload_file(upload_path_from_name(rest[0]))
      output.append(f"deleted {summary.filename} ({summary.bytes_written} bytes)")
      status = "ok"
    elif cmd == "touch":
      if not rest:
        raise HTTPException(status_code=400, detail="touch requires a filename")
      target_path = upload_path_from_name(rest[0])
      if not target_path.exists():
        summary = write_text_file(target_path, "")
        output.append(f"created {summary.filename}")
      else:
        target_path.touch()
        output.append(f"updated timestamp for {target_path.name}")
      status = "ok"
    elif cmd == "mv":
      if len(rest) != 2:
        raise HTTPException(status_code=400, detail="mv requires source and destination")
      summary = rename_upload_file(rest[0], rest[1])
      output.append(f"renamed to {summary.filename}")
      status = "ok"
    else:
      return UploadCommandResponse(command=command, output=[], status="unknown", error=f"Unsupported command: {cmd}")
  except HTTPException as exc:
    return UploadCommandResponse(command=command, output=[], status="error", error=exc.detail if isinstance(exc.detail, str) else str(exc.detail))

  return UploadCommandResponse(command=command, output=output, status=status)


def render_markdown(content: str) -> str:
  return markdown.markdown(content, extensions=["extra", "sane_lists", "smarty"])


def resolve_upload_path(raw_path: str) -> Path:
  raw_path = raw_path.lstrip("/\\")
  candidate = (UPLOAD_DIR / raw_path).resolve()
  try:
    candidate.relative_to(UPLOAD_DIR.resolve())
  except ValueError as exc:
    raise HTTPException(status_code=400, detail="Path escapes uploads directory") from exc
  return candidate


def relative_from_uploads(path: Path) -> str:
  return str(path.relative_to(UPLOAD_DIR.resolve()))


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


@app.get("/motd/html", response_class=HTMLResponse, tags=["content"])
async def motd_html_view(path: Path = Depends(motd_dependency)) -> HTMLResponse:
  try:
    content = path.read_text(encoding="utf-8")
  except OSError as exc:
    raise HTTPException(status_code=500, detail=f"Failed to read MOTD: {exc}") from exc
  html = render_markdown(content)
  return HTMLResponse(content=html)


@app.put("/motd", response_model=MotdUpdateResponse, tags=["content"])
async def motd_update(payload: TextFilePayload, path: Path = Depends(motd_dependency)) -> MotdUpdateResponse:
  summary = write_text_file(path, payload.content)
  stat = path.stat()
  return MotdUpdateResponse(
    message="MOTD updated",
    bytes_written=summary.bytes_written,
    updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
  )


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
  file_path = upload_path_from_name(filename)
  if not file_path.exists() or not file_path.is_file():
    raise HTTPException(status_code=404, detail="File not found")
  return FileResponse(file_path)


@app.delete("/upload/{filename:path}", response_model=UploadSummary, tags=["uploads"])
async def upload_delete(filename: str) -> UploadSummary:
  file_path = upload_path_from_name(filename)
  return delete_upload_file(file_path)


@app.get("/upload/{filename:path}/text", response_model=TextFilePayload, tags=["uploads"])
async def upload_text(filename: str) -> TextFilePayload:
  file_path = upload_path_from_name(filename)
  content = read_text_file(file_path)
  return TextFilePayload(content=content)


@app.put("/upload/{filename:path}", response_model=UploadSummary, tags=["uploads"])
async def upload_put(filename: str, payload: TextFilePayload) -> UploadSummary:
  target_path = upload_path_from_name(filename)
  return write_text_file(target_path, payload.content)


@app.post("/upload/{filename:path}/rename", response_model=UploadSummary, tags=["uploads"])
async def upload_rename(filename: str, payload: RenamePayload) -> UploadSummary:
  return rename_upload_file(filename, payload.target)


@app.post("/uploads/command", response_model=UploadCommandResponse, tags=["uploads"])
async def upload_command(request: UploadCommandRequest) -> UploadCommandResponse:
  return run_upload_command(request.command)


@app.get("/fs/list", response_model=FSListResponse, tags=["uploads"])
async def fs_list(path: Optional[str] = Query(default=None, description="Subdirectory to list")) -> FSListResponse:
  target = resolve_upload_path(path or "")
  if not target.exists():
    raise HTTPException(status_code=404, detail="Directory not found")
  if target.is_file():
    raise HTTPException(status_code=400, detail="Path points to a file")

  items: List[FSListItem] = []
  for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
    stat = entry.stat()
    items.append(
      FSListItem(
        path=relative_from_uploads(entry),
        is_dir=entry.is_dir(),
        size_bytes=None if entry.is_dir() else stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
      )
    )
  return FSListResponse(items=items)


@app.get("/fs/read", response_model=TextFilePayload, tags=["uploads"])
async def fs_read(path: str = Query(description="File path relative to uploads root")) -> TextFilePayload:
  file_path = resolve_upload_path(path)
  content = read_text_file(file_path)
  return TextFilePayload(content=content)


@app.post("/fs/write", response_model=UploadSummary, tags=["uploads"])
async def fs_write(payload: FSWritePayload) -> UploadSummary:
  target_path = resolve_upload_path(payload.filename)
  return write_text_file(target_path, payload.content)


@app.delete("/fs/delete", response_model=UploadSummary, tags=["uploads"])
async def fs_delete(payload: FSDeletePayload) -> UploadSummary:
  target_path = resolve_upload_path(payload.filename)
  if target_path.is_dir():
    raise HTTPException(status_code=400, detail="Refusing to delete directories via API")
  return delete_upload_file(target_path)


@app.exception_handler(httpx.HTTPError)
async def httpx_error_handler(_: Any, exc: httpx.HTTPError) -> JSONResponse:
  return JSONResponse(status_code=502, content={"detail": f"External request failed: {exc}"})
