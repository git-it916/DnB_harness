"""Single local worker for long-running PDF/LLM review jobs."""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from src.application.alias_registry import AliasRegistry
from src.application.review_service import ReviewService
from src.client.anthropic_client import AnthropicJSONClient
from src.web_api.store import RunStore


class ReviewWorker:
    def __init__(self, store: RunStore):
        self.store = store
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="dnb-review-worker")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=5)

    def submit(self, run_id: str) -> None:
        self._queue.put(run_id)

    def _loop(self) -> None:
        while True:
            run_id = self._queue.get()
            if run_id is None:
                return
            try:
                self._run_one(run_id)
            except Exception as exc:  # worker boundary: persist concise error for UI
                self.store.fail(run_id, f"{type(exc).__name__}: {exc}")
            finally:
                self._queue.task_done()

    def _run_one(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        registry = AliasRegistry(self.store.database_path)
        service = ReviewService(
            extraction_client=AnthropicJSONClient(model=run["model"], max_tokens=8192),
            alias_lookup=registry,
        )
        result = service.run(
            run_id=run_id,
            contract_pdf=self.store.input_path(run_id, "contract"),
            im_pdf=self.store.input_path(run_id, "im"),
            strategy=run["strategy"],
            progress=lambda stage: self.store.set_progress(run_id, stage=stage),
        )
        self.store.complete(run_id, result)
