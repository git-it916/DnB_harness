"""FastAPI application for the local DnB Harness review workspace."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from src.application.alias_registry import AliasRegistry
from src.web_api.store import RunStore
from src.web_api.worker import ReviewWorker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ROOT = Path(os.getenv("DNB_LOCAL_ROOT", PROJECT_ROOT / "var"))
MAX_PDF_BYTES = 50 * 1024 * 1024


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    note: str = Field(default="", max_length=500)
    remember_alias: bool = False


def create_app(
    *,
    store: RunStore | None = None,
    worker: ReviewWorker | None = None,
) -> FastAPI:
    run_store = store or RunStore(LOCAL_ROOT / "dnb.sqlite3", LOCAL_ROOT / "runs")
    review_worker = worker or ReviewWorker(run_store)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        review_worker.start()
        yield
        review_worker.stop()

    app = FastAPI(title="DnB Harness Local Review API", version="0.1.0", lifespan=lifespan)
    app.state.store = run_store
    app.state.worker = review_worker
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "local_only": True}

    @app.get("/api/v1/runs")
    def list_runs():
        return run_store.list_runs()

    @app.post("/api/v1/runs", status_code=202)
    async def create_run(
        contract: UploadFile = File(...),
        im: UploadFile = File(...),
        strategy: str = Form("ontology_policy_judge"),
        model: str = Form("claude-sonnet-4-6"),
    ):
        if strategy not in ("ontology_policy", "ontology_policy_judge"):
            raise HTTPException(422, "지원하지 않는 검토 방식입니다.")
        run_id = f"review_{uuid.uuid4().hex[:12]}"
        try:
            run = run_store.create_run(
                run_id=run_id,
                strategy=strategy,
                model=model,
                contract_name=contract.filename or "contract.pdf",
                im_name=im.filename or "im.pdf",
            )
            await _save_pdf(contract, run_store.input_path(run_id, "contract"))
            await _save_pdf(im, run_store.input_path(run_id, "im"))
        except ValueError as exc:
            run_store.fail(run_id, str(exc))
            raise HTTPException(422, str(exc)) from exc
        review_worker.submit(run_id)
        return run

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str):
        try:
            run = run_store.get_run(run_id)
            result = run_store.load_result(run_id)
        except KeyError as exc:
            raise HTTPException(404, "검토 실행을 찾을 수 없습니다.") from exc
        return {**run, "result": result.model_dump(mode="json") if result else None}

    @app.get("/api/v1/runs/{run_id}/documents/{role}")
    def get_document(run_id: str, role: str):
        try:
            path = run_store.input_path(run_id, role)
        except (KeyError, ValueError) as exc:
            raise HTTPException(404, "문서를 찾을 수 없습니다.") from exc
        if not path.exists():
            raise HTTPException(404, "문서를 찾을 수 없습니다.")
        return FileResponse(path, media_type="application/pdf")

    @app.post("/api/v1/runs/{run_id}/fields/{field:path}/decision")
    def save_decision(run_id: str, field: str, payload: DecisionRequest):
        try:
            result = run_store.load_result(run_id)
        except KeyError as exc:
            raise HTTPException(404, "검토 실행을 찾을 수 없습니다.") from exc
        if result is None:
            raise HTTPException(409, "검토가 아직 완료되지 않았습니다.")
        target = next((item for item in result.fields if item.field == field), None)
        if target is None:
            raise HTTPException(404, "검토 필드를 찾을 수 없습니다.")
        try:
            if payload.remember_alias:
                if payload.decision != "same":
                    raise ValueError("동일 판정만 Alias로 저장할 수 있습니다.")
                if not target.contract.raw_text or not target.im.raw_text:
                    raise ValueError("양쪽 원문 근거가 있어야 Alias로 저장할 수 있습니다.")
                AliasRegistry(run_store.database_path).remember(
                    field=field,
                    left=target.contract.raw_text,
                    right=target.im.raw_text,
                    source_run_id=run_id,
                )
            run_store.save_decision(
                run_id=run_id,
                field=field,
                decision=payload.decision,
                note=payload.note,
                remember_alias=payload.remember_alias,
            )
            run_store.refresh_review_status(run_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        updated = run_store.load_result(run_id)
        return updated.model_dump(mode="json") if updated else None

    dist = PROJECT_ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            candidate = dist / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


async def _save_pdf(upload: UploadFile, destination: Path) -> None:
    total = 0
    first = True
    with destination.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            if first:
                first = False
                if not chunk.startswith(b"%PDF-"):
                    raise ValueError("PDF 파일만 업로드할 수 있습니다.")
            total += len(chunk)
            if total > MAX_PDF_BYTES:
                raise ValueError("PDF는 파일당 50MB를 넘을 수 없습니다.")
            output.write(chunk)
    if total == 0:
        raise ValueError("빈 파일은 업로드할 수 없습니다.")


app = create_app()
