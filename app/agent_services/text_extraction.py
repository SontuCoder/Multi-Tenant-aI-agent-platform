
from io import BytesIO

import fitz
from docx import Document as DocxDocument


def extract_pdf(file_bytes: bytes) -> str:
    extracted_text = []

    with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
        for page in pdf:
            text = page.get_text("text")

            if text.strip():
                extracted_text.append(text)

    return "\n\n".join(extracted_text)


def extract_docx(file_bytes: bytes) -> str:
    document = DocxDocument(BytesIO(file_bytes))

    extracted_text = []

    # Extract paragraphs
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            extracted_text.append(paragraph.text)

    # Extract tables
    for table in document.tables:
        for row in table.rows:
            row_text = [
                cell.text.strip()
                for cell in row.cells
            ]

            if any(row_text):
                extracted_text.append(" | ".join(row_text))

    return "\n".join(extracted_text)


def extract_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8-sig")


def extract_text(file_bytes: bytes, file_type: str) -> str:

    if file_type == "pdf":
        return extract_pdf(file_bytes)

    elif file_type == "docx":
        return extract_docx(file_bytes)

    elif file_type == "txt":
        return extract_txt(file_bytes)

    raise ValueError(f"Unsupported file type: {file_type}")
