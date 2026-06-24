from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.rag import router as rag_router
from app.api.pending import router as pending_router
from app.api.checklist import router as checklist_router
from app.api.admin import router as admin_router
from app.api.ocr import router as ocr_router

routers = [auth_router, documents_router, rag_router, pending_router, checklist_router, admin_router, ocr_router]
