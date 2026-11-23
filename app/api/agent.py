from fastapi import APIRouter, status, Depends, HTTPException
from sqlmodel import Session, select
from uuid import uuid4, UUID
from database import get_session, KnowledgeBase
from models import AgentResponse, AgentRequest
from services import search_similar_chunks, build_retrieval_text, build_retrieved_context

route = APIRouter(prefix="/api/agent", tags=["Agent"])

@route.post("/{tenant_id}/{knowledge_id}", status_code=status.HTTP_200_OK, response_model=AgentResponse)
def get_agent_response(tenant_id:UUID, knowledge_id: UUID, agent_request: AgentRequest, session: Session = Depends(get_session)):

    ## Tenant Verify Pending
    
    knowledge_base = session.get(
        KnowledgeBase,
        knowledge_id
    )

    if not knowledge_base:
        raise HTTPException(
            status_code=404,
            detail="Knowledge base not found"
        )
    if knowledge_base.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Knowledge base does not belong to this tenant"
        )
    
    question = ""
    if agent_request.mail_data:
        question = build_retrieval_text(agent_request.mail_data.subject, agent_request.mail_data.body, agent_request.mail_data.sender, agent_request.mail_data.to, agent_request.user_question)
    else:
        question=agent_request.user_question

    chunks = search_similar_chunks(session, question, tenant_id, knowledge_id)
    if not chunks:
        return AgentResponse(
            scenario="UNKNOWN",
            output_language=agent_request.output_language,
            ai_message="I could not find relevant information in the knowledge base."
        )

    chunks_text = build_retrieved_context(chunks)

    # Need edit every document has a column as Scenario

