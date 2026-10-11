"""HTTP API and demo page.  Install with: pip install ".[web]"

Run:  co-extract-web  (or python -m co_extract.web)  ->  http://127.0.0.1:8000

Endpoints
    GET  /                    demo page
    GET  /health              liveness
    GET  /api/schema          JSON Schema of the result
    POST /api/extract         multipart upload, field "file"  -> ExtractionResult
    POST /api/extract-text    {"text": "..."}                 -> ExtractionResult

Set CO_EXTRACT_WEB_LLM=1 (with ANTHROPIC_API_KEY) to add the LLM extractor as a fallback for
documents the rules leave needing review.
"""

from __future__ import annotations

import argparse
import logging
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from co_extract.errors import ChangeOrderError
from co_extract.loader import SUPPORTED_SUFFIXES
from co_extract.pipeline import ChangeOrderPipeline, build_pipeline
from co_extract.schema import ExtractionResult
from co_extract.web_page import PAGE

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_TEXT_CHARS = 200_000


class TextRequest(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)


def create_app(pipeline: ChangeOrderPipeline | None = None) -> FastAPI:
    pipeline = pipeline or build_pipeline(llm_fallback=os.environ.get("CO_EXTRACT_WEB_LLM") == "1")
    app = FastAPI(title="Change Order Extractor", version="1.0")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return PAGE

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/schema")
    def schema() -> dict[str, Any]:
        return ExtractionResult.model_json_schema()

    @app.post("/api/extract-text")
    def extract_text(request: TextRequest) -> ExtractionResult:
        if not request.text.strip():
            raise HTTPException(422, "text is empty")
        return pipeline.run_text(request.text, source="<pasted text>")

    @app.post("/api/extract")
    def extract_file(file: UploadFile = File(...)) -> ExtractionResult:  # noqa: B008
        name = Path(file.filename or "upload").name
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise HTTPException(415, f"unsupported file type {suffix!r}")
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"file larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / f"upload{suffix}"  # never trust the client's file name on disk
            path.write_bytes(data)
            try:
                result = pipeline.run_file(path)
            except ChangeOrderError as exc:
                raise HTTPException(422, str(exc).replace(str(path), name)) from exc
        return result.model_copy(update={"source": name})

    return app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="co-extract-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
