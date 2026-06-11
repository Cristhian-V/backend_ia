import re
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_reference import DocumentReference


class ReferenceService:
    def normalize(self, text: str) -> str:
        import unicodedata
        text = unicodedata.normalize("NFKD", text.lower())
        text = "".join(c for c in text if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]", "", text)

    async def process_references(
        self,
        db: AsyncSession,
        user_id: int,
        source_doc_id: str,
        all_references: list[list[dict]],
        all_chapters: list[list[dict]],
        filtered_titles: set[str] | None = None,
    ) -> int:
        flat_refs: list[dict] = []
        seen_keys = set()

        for i, refs in enumerate(all_references):
            chaps = all_chapters[i] if i < len(all_chapters) else []
            for ref in refs:
                key = self.normalize(ref["ref_number"] + ref.get("ref_article", ""))
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                ref["chapter_title"] = self._find_chapter_for_ref(ref, chaps)
                if self._is_legal_framework(ref["chapter_title"]):
                    continue
                if filtered_titles and ref["chapter_title"] in filtered_titles:
                    continue
                flat_refs.append(ref)

        existing_docs = await self._load_existing_docs(db, user_id)

        count = 0
        for ref in flat_refs:
            ref_number_nrm = self.normalize(ref["ref_number"])
            resolved_id = existing_docs.get(ref_number_nrm)

            db_ref = DocumentReference(
                user_id=user_id,
                source_document_id=source_doc_id,
                chapter_title=ref.get("chapter_title", ""),
                ref_type=self._normalize_ref_type(ref.get("ref_type", "otro")),
                ref_number=ref.get("ref_number", ""),
                ref_number_nrm=ref_number_nrm,
                ref_title=ref.get("ref_title", ""),
                ref_article=ref.get("ref_article", ""),
                ref_date=ref.get("ref_date", ""),
                relation=self._normalize_relation(ref.get("relation", "referencia")),
                resolved_document_id=resolved_id,
            )
            db.add(db_ref)
            count += 1

        await db.commit()
        return count

    async def resolve_existing_references(self, db: AsyncSession, new_doc_id: str, doc_number_nrm: str):
        if not doc_number_nrm:
            return
        await db.execute(
            update(DocumentReference)
            .where(
                DocumentReference.ref_number_nrm == doc_number_nrm,
                DocumentReference.resolved_document_id.is_(None),
            )
            .values(resolved_document_id=new_doc_id)
        )
        await db.commit()

    LEGAL_FRAMEWORK_TERMS = ["marco legal", "marco normativo", "base legal", "marco juridico"]

    VALID_REF_TYPES = {"resolucion", "circular", "ley", "decreto", "reglamento", "otro"}

    REF_TYPE_MAP = {
        "resolución": "resolucion",
        "resoluci\u00f3n": "resolucion",
        "decisión": "otro",
        "decisi\u00f3n": "otro",
        "decisional": "otro",
        "constitución": "otro",
        "constituci\u00f3n": "otro",
        "decreto supremo": "decreto",
        "decreto_supremo": "decreto",
        "resolución de directorio": "resolucion",
        "normativa": "otro",
        "documento": "otro",
    }

    def _normalize_ref_type(self, ref_type: str) -> str:
        t = ref_type.strip().lower()
        mapped = self.REF_TYPE_MAP.get(t, t)
        if mapped not in self.VALID_REF_TYPES:
            return "otro"
        return mapped

    def _normalize_relation(self, relation: str) -> str:
        r = relation.strip().lower()
        valid = {"deroga", "modifica", "referencia", "complementa", "base_legal"}
        if r in valid:
            return r
        if "derog" in r:
            return "deroga"
        if "modif" in r:
            return "modifica"
        if "complement" in r:
            return "complementa"
        if "base" in r or "legal" in r:
            return "base_legal"
        return "referencia"

    def _find_chapter_for_ref(self, ref: dict, chapters: list[dict]) -> str:
        if not chapters:
            return ""
        ref_num = self.normalize(ref.get("ref_number", ""))
        for ch in chapters:
            content = ch.get("content", "")
            if ref_num in self.normalize(content):
                return ch.get("title", "")
        return chapters[0].get("title", "") if chapters else ""

    def _is_legal_framework(self, chapter_title: str) -> bool:
        title = chapter_title.lower()
        return any(term in title for term in self.LEGAL_FRAMEWORK_TERMS)

    async def _load_existing_docs(self, db: AsyncSession, user_id: int) -> dict[str, str]:
        result = await db.execute(
            select(Document.id, Document.doc_number_nrm).where(
                Document.user_id == user_id,
                Document.status == "ready",
                Document.doc_number_nrm.isnot(None),
            )
        )
        return {row[1]: row[0] for row in result.all()}

    async def get_pending(
        self,
        db: AsyncSession,
        user_id: int,
        source_doc_id: str | None = None,
    ) -> list[dict]:
        query = select(DocumentReference).where(
            DocumentReference.user_id == user_id,
            DocumentReference.resolved_document_id.is_(None),
        )
        if source_doc_id:
            query = query.where(DocumentReference.source_document_id == source_doc_id)
        query = query.order_by(DocumentReference.created_at.desc())

        result = await db.execute(query)
        rows = result.scalars().all()

        doc_ids = list({r.source_document_id for r in rows})
        doc_names = {}
        if doc_ids:
            doc_result = await db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
            )
            for doc_id, name in doc_result.all():
                doc_names[doc_id] = name

        return [
            {
                "id": r.id,
                "source_doc_id": r.source_document_id,
                "source_filename": doc_names.get(r.source_document_id, r.source_document_id),
                "chapter_title": r.chapter_title,
                "ref_type": r.ref_type,
                "ref_number": r.ref_number,
                "ref_title": r.ref_title,
                "ref_article": r.ref_article,
                "ref_date": r.ref_date,
                "relation": r.relation,
                "resolved": r.resolved_document_id is not None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

    async def get_grouped_pending(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> list[dict]:
        query = (
            select(DocumentReference)
            .where(DocumentReference.user_id == user_id)
            .order_by(DocumentReference.ref_type, DocumentReference.ref_number_nrm, DocumentReference.created_at)
        )
        result = await db.execute(query)
        rows = result.scalars().all()

        doc_names = {}
        all_doc_ids = list({r.source_document_id for r in rows})
        if all_doc_ids:
            doc_result = await db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(all_doc_ids))
            )
            for doc_id, name in doc_result.all():
                doc_names[doc_id] = name

        groups: dict[str, dict] = {}
        for r in rows:
            key = f"{r.ref_type}|{r.ref_number_nrm}|{self.normalize(r.ref_title)}"
            if key not in groups:
                groups[key] = {
                    "ref_type": r.ref_type,
                    "ref_number": r.ref_number,
                    "ref_title": r.ref_title,
                    "relation": r.relation,
                    "resolved": r.resolved_document_id is not None,
                    "refs": [],
                    "ref_ids": [],
                }
            groups[key]["refs"].append({
                "ref_id": r.id,
                "chapter_title": r.chapter_title,
                "ref_article": r.ref_article,
                "source_filename": doc_names.get(r.source_document_id, r.source_document_id),
            })
            groups[key]["ref_ids"].append(r.id)
            if r.resolved_document_id is not None:
                groups[key]["resolved"] = True

        return list(groups.values())


reference_service = ReferenceService()
