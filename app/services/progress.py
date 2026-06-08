import asyncio
from typing import Optional


class ProgressTracker:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._progress: dict[str, dict] = {}

    async def init(self, doc_id: str, total: int = 0, message: str = "Iniciando..."):
        async with self._lock:
            self._progress[doc_id] = {
                "status": "processing",
                "stage": "starting",
                "current": 0,
                "total": total,
                "message": message,
                "pages": 0,
                "chunks_found": 0,
                "error": None,
            }

    async def update(self, doc_id: str, stage: str, current: int, total: int, message: str, **extra):
        async with self._lock:
            if doc_id not in self._progress:
                self._progress[doc_id] = {
                    "status": "processing",
                    "stage": stage,
                    "current": current,
                    "total": total,
                    "message": message,
                    "pages": extra.get("pages", 0),
                    "chunks_found": extra.get("chunks_found", 0),
                    "error": None,
                }
            else:
                p = self._progress[doc_id]
                p["stage"] = stage
                p["current"] = current
                p["total"] = total
                p["message"] = message
                for key in ("pages", "chunks_found"):
                    if key in extra:
                        p[key] = extra[key]

    async def set_error(self, doc_id: str, error: str):
        async with self._lock:
            if doc_id in self._progress:
                self._progress[doc_id]["status"] = "error"
                self._progress[doc_id]["error"] = error

    async def set_done(self, doc_id: str, chunks: int = 0):
        async with self._lock:
            if doc_id in self._progress:
                self._progress[doc_id]["status"] = "ready"
                self._progress[doc_id]["stage"] = "done"
                self._progress[doc_id]["message"] = "Completado"
                self._progress[doc_id]["chunks_found"] = chunks

    async def get(self, doc_id: str) -> Optional[dict]:
        async with self._lock:
            return self._progress.get(doc_id)

    async def remove(self, doc_id: str):
        async with self._lock:
            self._progress.pop(doc_id, None)


progress_tracker = ProgressTracker()
