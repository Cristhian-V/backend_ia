from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, Base
from app.core.security import hash_password
from app.models.user import User
from app.models.document import Document
from app.models.query_log import QueryLog
from app.models.document_reference import DocumentReference
from app.models.document_chunk import DocumentChunk
from app.models.user_tool import UserTool
from app.models.checklist import Checklist
from app.services.vector_store import vector_store
from app.api.router import routers
from app.constants import TOOL_KEYS


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
        await conn.run_sync(Base.metadata.create_all)

    # seed admin if none exists
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM auth.users WHERE is_admin = TRUE"))
            count = result.scalar()
            if count == 0:
                email = os.getenv("ADMIN_EMAIL", "admin@hermes.com")
                password = os.getenv("ADMIN_PASSWORD", "admin123")
                hashed = hash_password(password)
                await conn.execute(
                    text("INSERT INTO auth.users (email, hashed_password, full_name, is_admin) VALUES (:email, :pass, 'Admin', TRUE)"),
                    {"email": email, "pass": hashed},
                )
                await conn.execute(
                    text(
                        "INSERT INTO core.user_tools (user_id, tool_key, role) "
                        "SELECT u.id, t.tk, t.rl FROM auth.users u "
                        "CROSS JOIN (VALUES (:t1, :r1), (:t2, NULL)) AS t(tk, rl) "
                        "WHERE u.is_admin = TRUE"
                    ),
                    {"t1": TOOL_KEYS[0], "r1": "gestor", "t2": TOOL_KEYS[1]},
                )
                print(f"  🧑‍💼 Admin seed creado: {email}")
    except Exception as e:
        print(f"  ⚠️  Admin seed skipped: {e}")

    # seed checklist from normativa txt
    try:
        async with engine.begin() as conn:
            count_result = await conn.execute(text("SELECT COUNT(*) FROM core.checklist"))
            if count_result.scalar() == 0:
                from app.services.checklist_seed import seed_checklist
                seeded = await seed_checklist(conn)
                print(f"  📋 Checklist: {seeded} items sembrados")
    except Exception as e:
        print(f"  ⚠️  Checklist seed skipped: {e}")
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT id FROM core.documents"))
            valid_ids = {row[0] for row in result.all()}
        removed = vector_store.cleanup_orphans(valid_ids)
        if removed:
            print(f"  🧹 FAISS: {removed} chunks huerfanos eliminados ({len(valid_ids)} documentos validos)")
    except Exception:
        pass

    # Start reference extraction scheduler (background)
    from app.services.reference_scheduler import scheduler_loop, log as sched_log
    scheduler_task = asyncio.create_task(scheduler_loop())
    sched_log("📅 Scheduler de referencias registrado")

    yield

    if scheduler_task and not scheduler_task.done():
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Hermes",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in routers:
    app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
