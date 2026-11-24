
from core import settings
from openai import OpenAI

EMBEDDING_MODEL = settings.OPENAI_EMBEDDING_MODEL
EMBEDDING_DIMENSIONS = settings.EMBEDDING_DIMENSIONS
BATCH_SIZE = settings.BATCH_SIZE
OPENAI_API_KEY = settings.OPENAI_API_KEY

client = OpenAI(
    api_key=OPENAI_API_KEY
)


def generate_embeddings(texts: list[str]) -> list[list[float]]:

    if not texts:
        return []

    embeddings = []

    for start in range(0, len(texts), BATCH_SIZE):

        batch = texts[start:start + BATCH_SIZE]

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
            dimensions=EMBEDDING_DIMENSIONS
        )

        batch_embeddings = sorted(
            response.data,
            key=lambda item: item.index
        )

        embeddings.extend(
            item.embedding
            for item in batch_embeddings
        )

    return embeddings
