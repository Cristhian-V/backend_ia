import json
import os

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


async def process_and_store(
    filename: str,
    content: bytes,
    doc_id: str,
    pages: list[str],
    on_progress=None,
) -> int:
    from app.services.window_service import window_service, PageWindow
    from app.services.chapter_service import chapter_service
    from app.services.merge_service import merge_service

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

    windows = window_service.create_windows(pages)
    total_windows = len(windows)
    await report("windowing", 1, 1, f"Ventanas creadas: {total_windows} lotes de 5 paginas")

    all_chapters = []
    for i, window in enumerate(windows):
        batch_num = i + 1
        await report(
            "detecting",
            batch_num,
            total_windows,
            f"Lote {batch_num}/{total_windows} → gemma4:e4b-32k detectando capitulos (pag {window.page_start + 1}-{window.page_end + 1})...",
            chunks_found=sum(len(c) for c in all_chapters),
        )
        try:
            chapters = await chapter_service.detect_chapters(window)
            for ch in chapters:
                ch["page_start"] = window.page_start
                ch["page_end"] = window.page_end
            all_chapters.append(chapters)
            print(f"     ↳ {len(chapters)} capitulos detectados: {', '.join(ch['title'][:40] for ch in chapters)}")
        except Exception as e:
            raise Exception(f"Error al procesar lote {batch_num} de {total_windows}: {e}")

    total_detected = sum(len(c) for c in all_chapters)
    await report(
        "merging",
        1,
        1,
        f"Merge y deduplicacion... {total_detected} capitulos detectados en bruto",
        chunks_found=total_detected,
    )

    merged_chapters = merge_service.merge(all_chapters)
    print(f"     ↳ {len(merged_chapters)} capitulos tras dedup (eliminados {total_detected - len(merged_chapters)})")

    if not merged_chapters:
        return 0

    texts = [ch["content"] for ch in merged_chapters]

    await report(
        "embedding",
        1,
        1,
        f"Generando embeddings con bge-m3 para {len(texts)} capitulos...",
        chunks_found=len(texts),
    )
    embeddings = await ollama_service.embed(texts)
    print(f"     ↳ {len(embeddings)} embeddings generados (dim=1024)")

    chunk_metadata = [
        {
            "title": ch.get("title", ""),
            "page_start": ch.get("page_start", 0),
            "page_end": ch.get("page_end", 0),
        }
        for ch in merged_chapters
    ]

    await report(
        "storing",
        1,
        1,
        f"Guardando {len(texts)} capitulos en FAISS...",
        chunks_found=len(texts),
    )
    vector_store.add_document(doc_id, texts, embeddings, chunk_metadata, filename=filename)

    print(f"{'='*60}")
    print(f"  ✅ COMPLETADO: {len(texts)} capitulos indexados")
    print(f"  📊 {total_pages} paginas → {total_windows} lotes → {len(texts)} chunks finales")
    print(f"{'='*60}\n")

    return len(texts)


vector_store = VectorStore()
