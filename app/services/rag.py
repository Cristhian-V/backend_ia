from app.services.ollama import ollama_service
from app.services.vector_store import vector_store


class RAGService:
    SYSTEM_PROMPT = (
        "Eres un experto en derecho aduanero boliviano. "
        "Responde unicamente basandote en el contexto proporcionado. "
        "Si el contexto no contiene informacion suficiente para responder, "
        "indicalo claramente y no inventes informacion. "
        "Cita el numero de normativa o articulo cuando este disponible. "
        "Responde en espanol, de forma clara y estructurada."
    )

    async def query(self, user_query: str, top_k: int | None = None) -> dict:
        query_embedding_list = await ollama_service.embed([user_query])
        query_embedding = query_embedding_list[0]

        results = vector_store.search(query_embedding, top_k)

        if not results:
            return {
                "answer": "No se encontraron documentos relevantes para tu consulta. Intenta subir normativas aduaneras primero.",
                "chunks": [],
                "model": ollama_service.chat_model,
            }

        context = "\n\n---\n\n".join(r["text"] for r in results)

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Contexto:\n{context}\n\nPregunta: {user_query}"},
        ]

        answer = await ollama_service.chat(messages)

        chunks = [
            {
                "doc_id": r["doc_id"],
                "text": r["text"][:300],
                "distance": r["distance"],
                "chapter_title": r.get("chapter_title", ""),
                "document_filename": r.get("original_filename", ""),
            }
            for r in results
        ]

        return {
            "answer": answer,
            "chunks": chunks,
            "model": ollama_service.chat_model,
        }


rag_service = RAGService()
