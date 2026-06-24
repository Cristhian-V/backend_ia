import asyncio
import os
from datetime import datetime as dt, time

from app.core.database import async_session
from app.models.document import Document
from app.models.document_reference import DocumentReference
from app.services.vector_store import vector_store
from app.services.chapter_service import chapter_service
from app.services.reference_service import reference_service
from sqlalchemy import select


SCHEDULE_START = time(22, 0)   # 10:00 PM
SCHEDULE_END = time(6, 0)     # 6:00 AM
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "reference_extraction.log")

running = False
paused = False


def log(msg: str):
    ts = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_in_window() -> bool:
    now = dt.now().time()
    if SCHEDULE_START < SCHEDULE_END:
        return SCHEDULE_START <= now <= SCHEDULE_END
    else:
        return now >= SCHEDULE_START or now <= SCHEDULE_END


async def extract_references_for_document(doc_id: str, filename: str) -> tuple[list[list[dict]], list[list[dict]], set[str]]:
    chunks = vector_store.get_document_chunks(doc_id)
    if not chunks:
        log(f"  ⚠️  {filename}: sin chunks en FAISS")
        return [], [], set()

    all_references = []
    all_chapters = []
    processed = 0
    with_refs = 0

    for idx, chunk in enumerate(chunks):
        chunk_text = chunk.get("text", "")
        chunk_title = chunk.get("chapter_title", "") or f"Chunk-{idx}"

        try:
            llm_title, refs = await chapter_service.extract_references(chunk_title, chunk_text)
            processed += 1
            if llm_title and llm_title != chunk_title:
                vector_store.update_chunk_title(doc_id, idx, llm_title)
            if refs:
                all_references.append(refs)
                all_chapters.append([{"title": chunk_title, "content": chunk_text}])
                with_refs += 1
        except Exception as e:
            log(f"     ⚠️  Error en {chunk_title[:60]}: {e}")

    total_refs = sum(len(r) for r in all_references) if all_references else 0
    log(f"     📊 {filename}: {with_refs}/{processed} chunks con referencias, {total_refs} totales")

    return all_references, all_chapters, set()


async def process_pending_documents():
    """Process documents that have 0 references extracted."""
    global paused

    async with async_session() as db:
        # Find documents with no references
        with_refs = (
            select(DocumentReference.source_document_id).distinct()
        )
        result = await db.execute(
            select(Document)
            .where(
                Document.status == "ready",
                Document.id.not_in(with_refs),
            )
            .order_by(Document.created_at)
        )
        docs = result.scalars().all()

    if not docs:
        log("  ✅ Todos los documentos tienen referencias extraidas")
        return

    log(f"  📋 {len(docs)} documentos pendientes de extraccion de referencias")

    for doc in docs:
        if paused:
            log(f"  ⏸️  Pausado. Reanudando en la siguiente ventana.")
            break

        if not is_in_window():
            log(f"  ⏰ Fuera de la ventana ({SCHEDULE_START} - {SCHEDULE_END}). Pausando...")
            paused = True
            break

        log(f"  📄 Procesando: {doc.filename}")

        try:
            all_references, all_chapters, filtered_titles = await extract_references_for_document(doc.id, doc.filename)

            if all_references:
                async with async_session() as db:
                    await reference_service.process_references(
                        db, doc.user_id, doc.id, all_references, all_chapters, filtered_titles
                    )
                    await reference_service.resolve_existing_references(
                        db, doc.id, ""
                    )
                total_refs = sum(len(r) for r in all_references)
                log(f"  ✅ {doc.filename}: {total_refs} referencias guardadas")
        except Exception as e:
            log(f"  ❌ Error procesando {doc.filename}: {e}")


async def scheduler_loop():
    global running, paused

    if running:
        return
    running = True
    log("🔄 Scheduler de referencias iniciado")

    while True:
        try:
            if is_in_window() and paused:
                log("▶️  Reanudando procesamiento...")
                paused = False

            if is_in_window() and not paused:
                await process_pending_documents()

            await asyncio.sleep(300)
        except Exception as e:
            log(f"⚠️  Error en scheduler: {e}")
            await asyncio.sleep(300)


def start_scheduler():
    asyncio.create_task(scheduler_loop())
    log("📅 Scheduler de referencias registrado")
