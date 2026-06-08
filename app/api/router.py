from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.rag import router as rag_router

routers = [auth_router, documents_router, rag_router]
