from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    DATABASE_URL: str
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str
    EMBEDDING_DIMENSIONS: int
    BATCH_SIZE: int
    NEON_STORAGE_BUCKET: str
    AWS_ENDPOINT_URL_S3: str
    AWS_REGION: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    TEXT_GENERATE_AI_MODEL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: str
    JWT_ISSUER:str
    JWT_AUDIENCE:str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
