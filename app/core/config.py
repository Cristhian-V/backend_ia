from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://192.168.1.10:11434"
    embed_model: str = "bge-m3:latest"
    chat_model: str = "gemma4:e4b-32k"
    ocr_model: str = "gemma4:26b-32k"

    jwt_public_key_file: str = "jwt-public.pem"

    database_url: str = "postgresql+asyncpg://cumbre:cumbre123@localhost:5432/cumbre_ia"
    chroma_persist_dir: str = "./chroma_data"

    top_k: int = 5

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
