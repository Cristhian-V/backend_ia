import json
import os
import re

import numpy as np
import faiss

from app.core.config import settings
from app.services.ollama import ollama_service


class VectorStore:
    def __init__(self):
        self.dim = 1024
        self.index_path = os.path.join(settings.chroma_persist_dir, "faiss.index")
        self.meta_path = os.path.join(settings.chroma_persist_dir, "metadata.json")
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        self.index = self._load_index()
        self.metadata: dict[str, dict] = self._load_metadata()

    def _load_index(self):
        if os.path.exists(self.index_path):
            return faiss.read_index(self.index_path)
        index = faiss.IndexFlatIP(self.dim)
        return index

    def _save_index(self):
        faiss.write_index(self.index, self.index_path)

    def _load_metadata(self) -> dict[str, dict]:
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_metadata(self):
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False)

    def add_document(
        self,
        doc_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        chunk_metadata: list[dict] | None = None,
        filename: str = "",
    ) -> None:
        vectors = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(vectors)
        start_id = self.index.ntotal
        self.index.add(vectors)
        for i, chunk in enumerate(chunks):
            faiss_id = start_id + i
            entry = {
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunk,
                "original_filename": filename,
            }
            if chunk_metadata and i < len(chunk_metadata):
                entry["chapter_title"] = chunk_metadata[i].get("title", "")
                entry["page_start"] = chunk_metadata[i].get("page_start", 0)
                entry["page_end"] = chunk_metadata[i].get("page_end", 0)
            self.metadata[str(faiss_id)] = entry
        self._save_index()
        self._save_metadata()

    def delete_document(self, doc_id: str) -> None:
        ids_to_delete = [
            int(fid) for fid, meta in self.metadata.items() if meta["doc_id"] == doc_id
        ]
        if not ids_to_delete:
            return

        keep_mask = np.ones(self.index.ntotal, dtype=bool)
        keep_mask[ids_to_delete] = False
        keep_indices = np.where(keep_mask)[0]

        if len(keep_indices) == 0:
            self.index = faiss.IndexFlatIP(self.dim)
            self.metadata = {}
        else:
            old_vectors = np.zeros((self.index.ntotal, self.dim), dtype=np.float32)
            self.index.reconstruct_n(0, self.index.ntotal, old_vectors)
            new_vectors = old_vectors[keep_indices]

            new_index = faiss.IndexFlatIP(self.dim)
            new_index.add(new_vectors)

            new_metadata = {}
            for new_i, old_i in enumerate(keep_indices):
                old_key = str(old_i)
                if old_key in self.metadata:
                    new_metadata[str(new_i)] = self.metadata[old_key]

            self.index = new_index
            self.metadata = new_metadata

        self._save_index()
        self._save_metadata()

    def update_chunk_title(self, doc_id: str, chunk_index: int, new_title: str) -> None:
        for fid, meta in self.metadata.items():
            if meta.get("doc_id") == doc_id and meta.get("chunk_index") == chunk_index:
                meta["chapter_title"] = new_title
        self._save_metadata()

    def get_document_chunks(self, doc_id: str) -> list[dict]:
        items = []
        for fid, meta in self.metadata.items():
            if meta.get("doc_id") == doc_id:
                items.append({
                    "id": fid,
                    "doc_id": meta["doc_id"],
                    "chunk_index": meta["chunk_index"],
                    "text": meta["text"],
                    "chapter_title": meta.get("chapter_title", ""),
                    "page_start": meta.get("page_start", 0),
                    "page_end": meta.get("page_end", 0),
                })
        items.sort(key=lambda x: x["chunk_index"])
        return items

    def search(self, query_embedding: list[float], top_k: int | None = None) -> list[dict]:
        k = min(top_k or settings.top_k, self.index.ntotal)
        if k == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)

        distances, indices = self.index.search(query, k)

        items = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            meta = self.metadata.get(str(idx))
            if meta:
                items.append({
                    "id": str(idx),
                    "doc_id": meta["doc_id"],
                    "chunk_index": meta["chunk_index"],
                    "text": meta["text"],
                    "distance": float(dist),
                    "chapter_title": meta.get("chapter_title", ""),
                    "original_filename": meta.get("original_filename", ""),
                })
        return items


TITLE_ONE_WHITELIST = {5, 6, 7}
TITLE_ONE_MAX = 8


async def process_and_store(
    filename: str,
    content: bytes,
    doc_id: str,
    pages: list[str],
    on_progress=None,
    extract_references: bool = True,
) -> tuple[int, list[list[dict]], list[list[dict]], set[str], dict]:
    from app.services.article_splitter import article_splitter
    from app.services.chapter_service import chapter_service

    full_text = "\n".join(pages)
    total_pages = len(pages)

    print(f"\n{'='*60}")
    print(f"  📄 PROCESANDO: {filename}")
    print(f"  📑 {total_pages} paginas extraidas")
    print(f"{'='*60}")

    async def report(stage: str, current: int, total: int, msg: str, **kw):
        print(f"  [{stage}] {msg}")
        if on_progress:
            await on_progress(stage, current, total, msg, **kw)

    await report("parsing", 1, 1, f"PDF parseado: {total_pages} paginas", pages=total_pages)

    raw_texts = article_splitter.split(full_text)
    total_raw = len(raw_texts)
    await report("splitting", 1, 1, f"Split por ARTICULO: {total_raw} fragmentos encontrados")

    articles = _filter_title_one_articles(raw_texts)
    if len(articles) < total_raw:
        print(f"     🔍 Filtrados {total_raw - len(articles)} articulos de TITULO I")

    filtered_titles: set[str] = set()
    for a in raw_texts:
        first_line = a.split("\n")[0].strip() if a else ""
        num = _extract_article_number(first_line)
        if num is not None and num not in TITLE_ONE_WHITELIST and _is_title_one_range(num):
            filtered_titles.add(first_line[:80])

    if not articles:
        return 0, [], [], filtered_titles, {}

    texts = articles

    await report("embedding", 1, 1, f"Generando embeddings con bge-m3 para {len(texts)} articulos...", chunks_found=len(texts))
    embeddings = await ollama_service.embed(texts)
    print(f"     ↳ {len(embeddings)} embeddings generados (dim=1024)")

    chunk_metadata = [{"title": a.split("\n")[0].strip() if a else "", "page_start": 0, "page_end": total_pages} for a in articles]

    await report("storing", 1, 1, f"Guardando {len(texts)} articulos en FAISS...", chunks_found=len(texts))
    vector_store.add_document(doc_id, texts, embeddings, chunk_metadata, filename=filename)

    all_references = []
    if extract_references:
        processed = 0
        with_refs = 0
        total_articles = len(articles)
        for i, text in enumerate(articles):
            title = text.strip().split("\n")[0].strip()[:80] if text else f"Chunk-{i}"

            await report("detecting", i + 1, total_articles, f"Extrayendo referencias de {title}...", chunks_found=len(texts))
            try:
                llm_title, refs = await chapter_service.extract_references(title, text)
                processed += 1
                if llm_title and llm_title != title:
                    vector_store.update_chunk_title(doc_id, i, llm_title)
                if refs:
                    all_references.append(refs)
                    with_refs += 1
                    print(f"     ↳ {title}: {len(refs)} referencias")
            except Exception as e:
                print(f"     ⚠️  Error en {title}: {e}")

        if processed > 0:
            print(f"     📊 Referencias: {with_refs}/{processed} articulos con referencias, {sum(len(r) for r in all_references)} totales")
        else:
            print(f"     ⚠️  No se proceso ningun articulo para referencias")
    else:
        print("     ⏭️  Extraccion de referencias omitida (toggle OFF)")

    doc_meta = _extract_doc_metadata_from_articles(articles)

    print(f"{'='*60}")
    print(f"  ✅ COMPLETADO: {len(texts)} articulos indexados")
    print(f"  📊 {total_pages} paginas → {len(articles)} articulos")
    print(f"  🔗 {sum(len(r) for r in all_references)} referencias detectadas")
    if doc_meta.get("doc_number"):
        print(f"  📋 Documento: {doc_meta.get('doc_type')} {doc_meta.get('doc_number')}")
    print(f"{'='*60}\n")

    return len(texts), [[{"title": a.split("\n")[0].strip()[:80], "content": a}] for a in articles], all_references, filtered_titles, doc_meta


def _extract_article_number(title: str) -> int | None:
    match = re.search(r"art[ií]culo\s+(\d+)", title.lower())
    if match:
        return int(match.group(1))
    return None


def _is_title_one_range(article_num: int) -> bool:
    return article_num <= TITLE_ONE_MAX


def _filter_title_one_articles(articles: list[str]) -> list[str]:
    result = []
    removed = 0
    for a in articles:
        first_line = a.split("\n")[0].strip() if a else ""
        if not first_line.lower().startswith("artic"):
            result.append(a)
            continue
        num = _extract_article_number(first_line)
        if num is not None and num not in TITLE_ONE_WHITELIST and _is_title_one_range(num):
            removed += 1
        else:
            result.append(a)
    if removed:
        print(f"     🔍 Filtrados {removed} articulos de TITULO I")
    return result


def _extract_doc_metadata_from_articles(articles: list[str]) -> dict:
    if not articles:
        return {}
    content = articles[0][:500]
    title = articles[0].split("\n")[0].strip() if articles[0] else ""

    doc_type = "otro"
    type_match = re.search(r"(resoluci[oó]n|circular|ley|decreto|reglamento)", title.lower())
    if not type_match:
        type_match = re.search(r"(resoluci[oó]n|circular|ley|decreto|reglamento)", content)
    if type_match:
        doc_type = type_match.group(1)

    doc_number = ""
    num_match = re.search(r"(?:N[°º]|No\.|numero)\s*[:.]?\s*([\d\/\-A-Za-z]+)", content, re.IGNORECASE)
    if not num_match:
        num_match = re.search(r"(?:RD|DS)\s*[:.]?\s*([\d\/\-]+)", content, re.IGNORECASE)
    if num_match:
        doc_number = num_match.group(0).strip()

    doc_title = ""
    for a in articles[:3]:
        line_match = re.search(r"^(?:RESOLUCI[OÓ]N|CIRCULAR|REGLAMENTO)[^.]*", a, re.IGNORECASE | re.MULTILINE)
        if line_match:
            doc_title = line_match.group(0).strip()[:200]
            break

    doc_date = ""
    date_match = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", content, re.IGNORECASE)
    if not date_match:
        date_match = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", content)
    if date_match:
        doc_date = date_match.group(0)

    issuing_body = ""
    body_match = re.search(r"(Aduana Nacional|Gerencia Nacional Jur[ií]dica|Presidente Ejecutivo|Directorio)", content, re.IGNORECASE)
    if body_match:
        issuing_body = body_match.group(1)

    return {
        "doc_type": doc_type,
        "doc_number": doc_number,
        "doc_number_nrm": re.sub(r"[^a-z0-9]", "", doc_number.lower()) if doc_number else "",
        "doc_title": doc_title,
        "doc_date": doc_date,
        "issuing_body": issuing_body or "",
    }


vector_store = VectorStore()
