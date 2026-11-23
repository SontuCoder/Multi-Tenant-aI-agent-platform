from uuid import UUID

from database import (
    get_background_session,
    Document,
    DocumentStatus,
    download_file
)

from .text_extraction import extract_text
from .text_cleaner import clean_text
from .chunking import chunk_text
from .text_embedding import generate_embeddings
from .vector_storage import store_chunks



def process_document(document_data: dict):

    document_id = UUID(document_data["id"])

    try:
        # Step 1: Download original file
        file_bytes = download_file(document_data["file_path"])

        # STEP 2: Extract text
        extracted_text = extract_text(
            file_bytes=file_bytes,
            file_type=document_data["file_type"]
        )

        if not extracted_text.strip():
            raise ValueError("No readable text found in document")

        # STEP 3: Clean extracted text
        cleaned_text = clean_text(extracted_text)

        if not cleaned_text:
            raise ValueError("Document contains no usable text")

        # STEP 4: Generate chunks
        chunks = chunk_text(cleaned_text)

        if not chunks:
            raise ValueError("No chunks generated")

        # STEP 5: Generate embeddings
        embeddings = generate_embeddings(chunks)

        # STEP 6: Store chunks and vectors
        total_chunks = store_chunks(
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings
        )

        return {
            "document_id": document_id,
            "status": "completed",
            "total_chunks": total_chunks
        }

    except Exception as exep:
        # Mark document as failed
        print(exep)
        with get_background_session() as session:

            document = session.get(Document, document_id)

            if (
                document
                and document.status == DocumentStatus.PROCESSING
            ):
                document.status = DocumentStatus.FAILED
                session.add(document)
                session.commit()

        raise
