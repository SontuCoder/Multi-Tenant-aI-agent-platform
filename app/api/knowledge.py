from fastapi import APIRouter, status, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from sqlmodel import Session, select
from uuid import uuid4, UUID
from pathlib import Path
from  hashlib import sha256
from database import get_session, KnowledgeBase, upload_file, delete_file, Document, DocumentStatus, FileType, get_background_session
from models import KnowledgeCreate, KnowledgeResponse, DocumentUploadResponse
from services import process_document

route = APIRouter(prefix="/api/knowledge-bases", tags=["Knowledge Base"])


@route.post("",status_code=status.HTTP_201_CREATED, response_model=KnowledgeResponse)
def create_knowledge(project:KnowledgeCreate, session: Session = Depends(get_session)):

    project_data = project.model_dump()
    project_data["name"] = project_data["name"].strip()
    tenant_id, name = project.tenant_id, project.name.strip()
    query = select(KnowledgeBase).where(KnowledgeBase.name == name, KnowledgeBase.tenant_id == tenant_id)
    existing_project = session.exec(query).first()

    if existing_project: 
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Current tenant already has a knowledge with this name."
        )

    new_project =KnowledgeBase(**project_data.model_dump())
    session.add(new_project)
    session.commit()
    session.refresh(new_project)
    return KnowledgeResponse.model_validate(new_project)

@route.get("/{project_id}", status_code=status.HTTP_200_OK, response_model=KnowledgeResponse)
def get_knowledge(project_id:UUID, session: Session = Depends(get_session)):
    query = select(KnowledgeBase).where(KnowledgeBase.id == project_id)
    existing_project = session.exec(query).first()

    if not existing_project:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge has been not found with this id."
            )
    return KnowledgeResponse.model_validate(existing_project)


MAX_FILE_SIZE = 20 * 1024 * 1024

CONTENT_TYPES = {
    ".pdf": (FileType.PDF, "application/pdf"),
    ".docx": (
        FileType.DOCX,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".txt": (FileType.TXT, "text/plain")
}

def save_document(
    file: UploadFile,
    knowledge_base,
    scenario: str | None,
    session
):
    extension = Path(file.filename or "").suffix.lower()

    if extension not in CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX and TXT are supported"
        )

    query = select(Document).where(Document.knowledge_base_id==knowledge_base.id, Document.filename==file.filename.strip())
    document = session.exec(query).first()
    if document:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Same name file already exist in this knowledge"
        )

    # Calculate hash and validate size
    file_hash = sha256()
    total_size = 0

    while True:
        content = file.file.read(1024 * 1024)

        if not content:
            break

        total_size += len(content)

        if total_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Maximum file size is 20 MB"
            )

        file_hash.update(content)

    if total_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    calculated_hash = file_hash.hexdigest()

    # Check duplicate inside this knowledge base
    duplicate_query = select(Document).where(
        Document.knowledge_base_id == knowledge_base.id,
        Document.tenant_id == knowledge_base.tenant_id,
        Document.file_hash == calculated_hash
    )

    if session.exec(duplicate_query).first():
        raise HTTPException(
            status_code=409,
            detail="Document already exists"
        )

    # Generate unique object key
    document_id = uuid4()

    object_key = (
        f"tenants/{knowledge_base.tenant_id}/"
        f"knowledge-bases/{knowledge_base.id}/"
        f"documents/{document_id}{extension}"
    )

    file_type, content_type = CONTENT_TYPES[extension]

    # Reset file pointer after hashing
    file.file.seek(0)

    uploaded = False

    try:
        # Upload actual file to Neon Object Storage
        upload_file(
            file_object=file.file,
            object_key=object_key,
            content_type=content_type
        )
        uploaded = True

        # Store only metadata and object key in PostgreSQL
        document = Document(
            id=document_id,
            knowledge_base_id=knowledge_base.id,
            tenant_id=knowledge_base.tenant_id,
            filename=file.filename.strip(),
            file_path=object_key,
            file_type=file_type,
            file_hash=calculated_hash,
            scenario=scenario,
            status=DocumentStatus.UPLOADED
        )

        session.add(document)
        session.commit()
        session.refresh(document)

        return document

    except Exception:
        session.rollback()

        # Compensate if the database insert fails
        if uploaded:
            try:
                delete_file(object_key)
            except Exception:
                # Log this failure and reconcile orphaned objects later.
                pass

        raise 

@route.post("/{knowledge_base_id}/documents", status_code=status.HTTP_201_CREATED, response_model=DocumentUploadResponse)
def upload_document(
    knowledge_base_id: UUID,
    file: UploadFile = File(...),
    scenario: str | None = Query(None),
    session: Session = Depends(get_session)
):
    knowledge_base = session.get(
        KnowledgeBase,
        knowledge_base_id
    )

    if not knowledge_base:
        raise HTTPException(
            status_code=404,
            detail="Knowledge base not found"
        )
    if scenario:
        scenario = scenario.strip().upper().replace(" ", "_")

    document = save_document(
        file=file,
        knowledge_base=knowledge_base,
        scenario=scenario,
        session=session
    )

    return DocumentUploadResponse.model_validate(document)

@route.get("/{knowledge_base_id}/documents", status_code=status.HTTP_200_OK, response_model=list[DocumentUploadResponse])
def get_documents(knowledge_base_id: UUID, session: Session = Depends(get_session)):
    knowledge_base = session.get(
        KnowledgeBase,
        knowledge_base_id
    )

    if not knowledge_base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    query = select(Document).where(Document.knowledge_base_id==knowledge_base_id)
    return session.exec(query).all()

@route.post("/{knowledge_base_id}/documents/{document_id}/process", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentUploadResponse)
def document_process(knowledge_base_id: UUID, document_id: UUID, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    knowledge_base = session.get(
        KnowledgeBase,
        knowledge_base_id
    )

    if not knowledge_base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    document = session.get(
        Document,
        document_id
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document is not found"
        )
    if document.knowledge_base_id != knowledge_base_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this knowledge base"
        )
    if document.status == DocumentStatus.PROCESSING:
        raise HTTPException(
            status_code=409,
            detail="Document is already processing"
        )
    if document.status == DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="Document already processed"
        )
    if document.status not in (DocumentStatus.UPLOADED, DocumentStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail="Document cannot be processed"
        )

    document.status = DocumentStatus.PROCESSING

    session.add(document)
    session.commit()
    session.refresh(document)

    document_data = {
        "id": str(document.id),
        "filename": document.filename,
        "file_path": document.file_path,
        "file_type": document.file_type.value,
        "scenario": document.scenario,
        "knowledge_base_id": str(document.knowledge_base_id),
        "tenant_id": str(document.tenant_id)
    }

    background_tasks.add_task(
        process_document,
        document_data
    )

    return DocumentUploadResponse.model_validate(document)


