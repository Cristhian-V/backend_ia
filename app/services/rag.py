from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_reference import DocumentReference
from app.services.ollama import ollama_service
from app.services.vector_store import vector_store


class RAGService:
    SYSTEM_PROMPT_SIMPLE = (
        "Eres un experto en derecho aduanero boliviano.\n\n"
        "El contexto incluye el documento fuente y documentos referenciados. "
        "Cada chunk esta etiquetado como [TITULO | NOMBRE DEL DOCUMENTO].\n\n"
        "INSTRUCCIONES ESTRICTAS:\n"
        "- Responde unicamente con el contenido del contexto. No inventes.\n"
        "- NO uses frases introductorias como 'Como experto...', 'A continuacion...'. "
        "Ve directo a la respuesta.\n"
        "- Al citar un articulo, incluye el nombre del documento: "
        "ej. 'Articulo 15 - Reglamento de Control Posterior'.\n\n"
        "Estructura tu respuesta en TRES secciones:\n\n"
        "### RESUMEN\n"
        "Parrafo de 2 a 4 lineas con la respuesta directa. Sin citas legales extensas, "
        "solo lo esencial que el operador necesita saber.\n\n"
        "### FUNDAMENTO LEGAL\n"
        "Tabla Markdown con columnas:\n"
        "| Articulo | Documento | Dispone que | Relacion |\n"
        "|----------|-----------|-------------|----------|\n"
        "Incluye tanto los articulos del documento principal como los referenciados.\n\n"
        "### IMPLICACIONES PRACTICAS PARA EL DESPACHO\n"
        "Vinietas con acciones concretas que el operador de comercio exterior debe realizar:\n"
        "- Obligaciones especificas (documentacion, plazos, registros)\n"
        "- Consecuencias de incumplimiento\n"
        "- Consideraciones operativas\n\n"
        "Usa Markdown (negritas, viñetas, tablas). Responde en espanol."
    )

    SYSTEM_PROMPT_TECNICA = (
        "Eres un experto en derecho aduanero boliviano.\n\n"
        "El contexto incluye el documento fuente y documentos referenciados. "
        "Cada chunk esta etiquetado como [TITULO | NOMBRE DEL DOCUMENTO].\n\n"
        "INSTRUCCIONES ESTRICTAS:\n"
        "- Responde unicamente con el contenido del contexto. No inventes.\n"
        "- NO uses frases introductorias como 'Como experto...', 'A continuacion...'. "
        "Ve directo a la respuesta.\n"
        "- Al citar un articulo, incluye el nombre del documento: "
        "ej. 'Articulo 15 - Reglamento de Control Posterior'.\n\n"
        "Estructura tu respuesta como una FICHA TECNICA con estas secciones:\n\n"
        "### TEMA\n"
        "Una linea con el tema central de la consulta.\n\n"
        "### RESPUESTA DIRECTA\n"
        "Dos a tres lineas con la respuesta concreta.\n\n"
        "### NORMAS APLICABLES\n"
        "Tabla Markdown:\n"
        "| Norma | Art. | Disposicion |\n"
        "|-------|------|-------------|\n\n"
        "### DETALLE POR ARTICULO\n"
        "Para cada articulo del contexto:\n"
        "**Articulo X - [Documento]**\n"
        "- Texto relevante: cita textual breve del articulo\n"
        "- Aplicacion a esta consulta: como se relaciona con lo preguntado\n\n"
        "### PUNTOS DE ATENCION\n"
        "Vinietas con riesgos, plazos ocultos, condiciones especiales o sanciones "
        "que el operador debe conocer.\n\n"
        "Usa Markdown (negritas, viñetas, tablas). Responde en espanol."
    )

    async def query(self, user_query: str, db: AsyncSession, top_k: int | None = None, response_mode: str = "simple") -> dict:
        query_embedding_list = await ollama_service.embed([user_query])
        query_embedding = query_embedding_list[0]

        results = vector_store.search(query_embedding, top_k)

        if not results:
            return {
                "answer": "No se encontraron documentos relevantes para tu consulta. Intenta subir normativas aduaneras primero.",
                "chunks": [],
                "model": ollama_service.chat_model,
            }

        extra_chunks = await self._resolve_references(db, results, user_query)
        all_results = results + extra_chunks

        # deduplicate by text prefix
        seen = set()
        unique = []
        for r in all_results:
            key = r["text"][:80]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        context_parts = []
        for r in unique:
            chunk_title = r.get("chapter_title", "") or ""
            doc_name = r.get("original_filename", "") or ""
            if chunk_title and doc_name:
                header = f"{chunk_title} | {doc_name}"
            else:
                header = chunk_title or doc_name
            context_parts.append(f"[{header}]\n{r['text']}")

        context = "\n\n---\n\n".join(context_parts)

        prompt = self.SYSTEM_PROMPT_SIMPLE if response_mode == "simple" else self.SYSTEM_PROMPT_TECNICA

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Contexto:\n{context}\n\nPregunta: {user_query}"},
        ]

        answer = await ollama_service.chat(messages)

        chunks = [
            {
                "doc_id": r["doc_id"],
                "text": r["text"][:300],
                "distance": r.get("distance", 0.0),
                "chapter_title": r.get("chapter_title", ""),
                "document_filename": r.get("original_filename", ""),
            }
            for r in unique
        ]

        return {
            "answer": answer,
            "chunks": chunks,
            "model": ollama_service.chat_model,
        }

    async def _resolve_references(self, db: AsyncSession, results: list[dict], user_query: str) -> list[dict]:
        extra: list[dict] = []
        seen_docs: set[str] = set()
        doc_filenames: dict[str, str] = {}
        max_articles = 5

        print(f"  [multi-hop] INICIO — {len(results)} resultados de FAISS")

        for i_r, r in enumerate(results):
            doc_id = r["doc_id"]
            print(f"  [multi-hop]   result {i_r}: doc_id={doc_id[:16]}... chapter_title={r.get('chapter_title','')[:60]}")

            if doc_id in seen_docs:
                print(f"  [multi-hop]   → ya visto, skip")
                continue
            seen_docs.add(doc_id)

            exists = await db.execute(
                select(Document.id).where(Document.id == doc_id).limit(1)
            )
            if not exists.scalar_one_or_none():
                print(f"  [multi-hop]   → doc_id NO existe en DB (huerfano), skip")
                continue

            refs_result = await db.execute(
                select(DocumentReference)
                .where(
                    DocumentReference.source_document_id == doc_id,
                    DocumentReference.resolved_document_id.isnot(None),
                )
                .limit(10)
            )
            refs = refs_result.scalars().all()
            print(f"  [multi-hop]   → {len(refs)} referencias resueltas encontradas")

            for i_ref, ref in enumerate(refs):
                if not ref.resolved_document_id:
                    print(f"  [multi-hop]     ref {i_ref}: sin resolved_document_id, skip")
                    continue

                articles = self._split_article_numbers(ref.ref_article)
                print(f"  [multi-hop]     ref {i_ref}: article={ref.ref_article[:30]} → nums={articles}")

                if not articles:
                    print(f"  [multi-hop]     → sin articulos, skip")
                    continue

                chunks = vector_store.get_document_chunks(ref.resolved_document_id)
                print(f"  [multi-hop]     → get_document_chunks('{ref.resolved_document_id[:16]}...') = {len(chunks)} chunks")

                for art_num in articles:
                    found = self._find_chunk_by_article(chunks, art_num)
                    if found:
                        print(f"  [multi-hop]     → art {art_num}: ENCONTRADO idx={found['chunk_index']}")
                        resolved_id = ref.resolved_document_id
                        if resolved_id not in doc_filenames:
                            fn_result = await db.execute(
                                select(Document.filename).where(Document.id == resolved_id)
                            )
                            doc_filenames[resolved_id] = fn_result.scalar_one_or_none() or ""
                        found["original_filename"] = doc_filenames[resolved_id]
                        extra.append(found)
                        break
                    else:
                        print(f"  [multi-hop]     → art {art_num}: NO ENCONTRADO en {len(chunks)} chunks")

                if len(extra) >= max_articles:
                    print(f"  [multi-hop]   → max_articles alcanzado ({max_articles})")
                    break

            if len(extra) >= max_articles:
                break

        if extra:
            print(f"  [multi-hop] FIN: {len(extra)} chunks extras")
        else:
            print(f"  [multi-hop] FIN: 0 chunks extras (vacio)")

        return extra

    def _find_chunk_by_article(self, chunks: list[dict], art_num: str) -> dict | None:
        nrm_num = self._normalize(art_num)
        for chunk in chunks:
            title_nrm = self._normalize(chunk.get("chapter_title", ""))
            if nrm_num in title_nrm:
                result = dict(chunk)
                result.setdefault("distance", 0.0)
                result.setdefault("original_filename", "")
                return result
        # fallback: search in chunk text
        for chunk in chunks:
            text_nrm = self._normalize(chunk.get("text", ""))
            if f"articulo {nrm_num}" in text_nrm:
                result = dict(chunk)
                result.setdefault("distance", 0.0)
                result.setdefault("original_filename", "")
                return result
        return None

    def _normalize(self, text: str) -> str:
        import unicodedata
        text = unicodedata.normalize("NFKD", text.lower())
        return "".join(c for c in text if not unicodedata.combining(c))

    def _split_article_numbers(self, ref_article: str) -> list[str]:
        import re
        if not ref_article or ref_article.upper() == "N/A":
            return []
        cleaned = ref_article.replace("Articulo", "").replace("Artículo", "").replace("Art.", "")
        numbers = re.findall(r"\d+", cleaned)
        return numbers


rag_service = RAGService()
