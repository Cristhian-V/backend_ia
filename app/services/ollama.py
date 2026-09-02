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
                        "temperature": 0.3,
                    },
                    "keep_alive": -1,
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def chat_with_images(self, images: list[str], prompt: str, model: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model or self.chat_model,
                    "prompt": prompt,
                    "images": images,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_predict": 32768,
                    },
                    "keep_alive": -1,
                },
            )
            resp.raise_for_status()
            return resp.json()["response"]


ollama_service = OllamaService()
