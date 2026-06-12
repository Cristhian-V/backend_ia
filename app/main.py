from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, Base
from app.models.user import User
from app.models.document import Document
from app.models.query_log import QueryLog
from app.models.document_reference import DocumentReference
from app.models.document_chunk import DocumentChunk
from app.services.vector_store import vector_store
from app.api.router import routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
        await conn.run_sync(Base.metadata.create_all)

    # clean FAISS orphans
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT id FROM core.documents"))
            valid_ids = {row[0] for row in result.all()}
        removed = vector_store.cleanup_orphans(valid_ids)
        if removed:
            print(f"  🧹 FAISS: {removed} chunks huerfanos eliminados ({len(valid_ids)} documentos validos)")
    except Exception:
        pass  # table might not exist on first run

    yield


app = FastAPI(
    title="Cumbre IA - RAG Aduanero",
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
