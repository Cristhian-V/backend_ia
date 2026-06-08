import httpx

from app.core.config import settings


class OllamaService:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.embed_model = settings.embed_model
        self.chat_model = settings.chat_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.embed_model, "input": texts, "keep_alive": -1},
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]

    async def chat(self, messages: list[dict]) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_ctx": 32768,
                    },
                    "keep_alive": -1,
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.base_url)
                return resp.is_success
        except httpx.RequestError:
            return False


ollama_service = OllamaService()
