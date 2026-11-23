
from uuid import UUID
from database import get_background_session
from services.semantic_search import search_similar_chunks

tenant_id = UUID("6322f08c-e261-4733-9127-4c7490d5eea5")
knowledge_base_id = UUID("7d099ed6-82d7-46d9-b423-04eaf3197f6c")

search_text = """
Question: what is objectives of this projects?.
"""

with get_background_session() as session:

    results = search_similar_chunks(
        session=session,
        question=search_text,
        tenant_id=tenant_id,
        knowledge_base_id=knowledge_base_id,
        top_k=5,
    )

    for result in results:
        print("Chunk:", result.chunk_id)
        print("Distance:", result.distance)
        print("Text:", result.chunk_text)
        print("-" * 50)
