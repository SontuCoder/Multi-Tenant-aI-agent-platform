
from uuid import uuid4

from sqlmodel import select

from database import (
    get_background_session,
    Document,
    DocumentChunk,
    DocumentStatus
)


def store_chunks(
    document_id,
    chunks: list[str],
    embeddings: list[list[float]]
):

    if len(chunks) != len(embeddings):
        raise ValueError(
            "Number of chunks and embeddings must match"
        )

    with get_background_session() as session:

        document = session.get(Document, document_id)

        if not document:
            raise ValueError("Document not found")

        if document.status != DocumentStatus.PROCESSING:
            raise ValueError("Document is not in PROCESSING state")

        # Remove previous chunks if this is a retry
        existing_chunks = session.exec(
            select(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            )
        ).all()

        for existing_chunk in existing_chunks:
            session.delete(existing_chunk)

        # Create new chunk records
        chunk_records = []

        for index, (chunk_text, embedding) in enumerate(
            zip(chunks, embeddings)
        ):

            chunk_record = DocumentChunk(
                id=uuid4(),
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                tenant_id=document.tenant_id,
                chunk_index=index,
                chunk_text=chunk_text,
                embedding=embedding,
                scenario=document.scenario,
                chunk_metadata={
                    "filename": document.filename,
                    "chunk_index": index
                }
            )

            chunk_records.append(chunk_record)

        session.add_all(chunk_records)

        document.status = DocumentStatus.COMPLETED
        session.add(document)

        session.commit()

        return len(chunk_records)
