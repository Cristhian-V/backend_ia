# F.A.R.O. — Backend (Python)

**Framework de Asistencia, Respuesta y Operaciones**

Backend principal de F.A.R.O. encargado del RAG (Retrieval-Augmented Generation), almacenamiento vectorial con FAISS, procesamiento de documentos PDF/DOCX, extracción de referencias normativas y consulta al LLM vía Ollama.

## Stack

- **FastAPI** + **Uvicorn** (async)
- **SQLAlchemy 2.0** + **asyncpg** (PostgreSQL)
- **FAISS** (`faiss-cpu`) — almacenamiento vectorial (IndexFlatIP)
- **Ollama** — embeddings (`bge-m3:latest`) + chat (`gemma4:26b-32k`)
- **pypdf** / **python-docx** — parsing de documentos
- **JWT** (python-jose) — autenticación compartida con backend_node

## Requisitos

- Python 3.13+
- PostgreSQL 16+ (puerto 5432 dev / 5433 prod)
- Ollama con modelos `bge-m3:latest` y `gemma4:26b-32k` instalados

## Instalación (dev)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

Crear `.env` en `backend/`:

```env
OLLAMA_BASE_URL=http://192.168.1.10:11434
EMBED_MODEL=bge-m3:latest
CHAT_MODEL=gemma4:26b-32k
SECRET_KEY=change-me-to-a-random-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=postgresql+asyncpg://cumbre:cumbre123@localhost:5432/cumbre_ia_test
CHROMA_PERSIST_DIR=./chroma_data
TOP_K=10
```

> `SECRET_KEY` debe ser identico al del `backend_node` para que JWT funcione entre ambos servicios.

## Comandos

```bash
# Servidor dev
uvicorn app.main:app --reload --port 8000

# Tests
python -m pytest tests/ -q
```

## Estructura

```
backend/
├── app/
│   ├── main.py                  # Lifespan: crea schemas, seed admin, seed checklist, cleanup FAISS, scheduler
│   ├── constants.py             # Enums compartidos: TOOL_KEYS, ROLES, RELATION_TYPES, REF_TYPES
│   ├── core/
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Engine + session async
│   │   └── security.py          # JWT, hash/verify password, get_current_user
│   ├── models/                  # SQLAlchemy (schema "core" y "auth")
│   │   ├── user.py              # auth.users
│   │   ├── user_tool.py         # core.user_tools (tool_key + role)
│   │   ├── document.py          # core.documents
│   │   ├── document_chunk.py    # core.document_chunks
│   │   ├── document_reference.py# core.document_references
│   │   ├── query_log.py         # core.query_logs
│   │   └── checklist.py         # core.checklist
│   ├── schemas/                 # Pydantic (request/response)
│   ├── api/                     # Routers FastAPI
│   │   ├── auth.py              # /auth/register, /auth/login, /auth/me
│   │   ├── documents.py         # /documents/ (upload, list, chunks, delete, progress)
│   │   ├── rag.py               # /rag/query, /rag/history
│   │   ├── pending.py           # /pending/grouped, /pending/{id}/resolve (cascade)
│   │   ├── checklist.py         # /checklist/stats, /checklist/
│   │   └── admin.py             # /admin/process-references (trigger manual)
│   ├── services/
│   │   ├── rag.py               # RAG query + multi-hop + prompts (simple/tecnica)
│   │   ├── vector_store.py      # FAISS CRUD + process_and_store + metadata extraction
│   │   ├── reference_service.py # Extraccion, grouping, resolve cascade
│   │   ├── reference_scheduler.py# Scheduler nocturno (22:00-06:00)
│   │   ├── chapter_service.py   # LLM: extrae titulo + referencias por chunk
│   │   ├── article_splitter.py  # PDF → chunks (cascade regex)
│   │   ├── ollama.py            # Cliente HTTP Ollama (embed + chat)
│   │   ├── parser.py            # PDF/DOCX → texto
│   │   ├── progress.py          # ProgressTracker (upload progress)
│   │   └── checklist_seed.py    # Seed checklist desde normativa_aduana_vigente.txt
│   └── data/
│       └── normativa_aduana_vigente.txt  # Data source para checklist
├── tests/                       # pytest (34 tests)
├── chroma_data/                 # FAISS: metadata.json + faiss.index
├── Dockerfile
└── requirements.txt
```

## API Endpoints

| Metodo | Ruta | Descripcion |
|---|---|---|
| POST | `/auth/register` | Registro (rol default: consultor) |
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Usuario actual + tools + roles |
| POST | `/documents/upload` | Subir PDF/DOCX (con progress polling) |
| GET | `/documents/` | Listar documentos |
| GET | `/documents/{id}/chunks` | Chunks de un documento |
| DELETE | `/documents/{id}` | Eliminar documento |
| GET | `/documents/{id}/progress` | Estado de procesamiento |
| POST | `/rag/query` | Consulta RAG (simple/tecnica) |
| GET | `/rag/history` | Historial del usuario |
| GET | `/rag/history/all` | Historial todos (admin) |
| GET | `/pending/grouped` | Referencias pendientes agrupadas |
| PUT | `/pending/{ref_id}/resolve` | Vincular/desvincular ref (cascade) |
| DELETE | `/pending/{ref_id}` | Eliminar referencia |
| GET | `/checklist/stats` | Estadisticas checklist |
| GET | `/checklist/` | Items checklist (filtros) |
| POST | `/admin/process-references` | Trigger extraccion manual (admin) |

## Puertos

| Entorno | Puerto |
|---|---|
| Dev | `8000` |
| Prod (Docker) | `8000` (host network) |
