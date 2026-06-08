from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://192.168.1.10:11434"
    embed_model: str = "bge-m3:latest"
    chat_model: str = "gemma4:e4b-32k"

    secret_key: str = "change-me-to-a-random-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    database_url: str = "postgresql+asyncpg://cumbre:cumbre123@localhost:5432/cumbre_ia"
    chroma_persist_dir: str = "./chroma_data"

    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5

    model_config = {"env_file": ".env"}


settings = Settings()
