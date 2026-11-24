from fastapi import APIRouter, status, Depends, HTTPException
from sqlmodel import Session
from uuid import UUID
from database import get_session, KnowledgeBase
from models import AgentRespones, AgentRequest
from agent_services import search_similar_chunks, build_retrieval_text, build_retrieved_context, build_agent_prompt, execute_agent, validate_agent_result

route = APIRouter(prefix="/api/agent", tags=["Agent"])

@route.post("/{tenant_id}/{knowledge_id}", status_code=status.HTTP_200_OK, response_model=AgentRespones)
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
        return AgentRespones(
            scenario="UNKNOWN",
            output_language=agent_request.output_language,
            ai_message="I could not find relevant information in the knowledge base."
        )

    chunks_text = build_retrieved_context(chunks)

    ai_prompt = build_agent_prompt(agent_request.mail_data, agent_request.input_language, agent_request.output_language, question, agent_request.user_prompt, chunks_text)
    # print(ai_prompt)
    agent_response = execute_agent(ai_prompt)
    print(agent_response)
    validate_ai_response = validate_agent_result(agent_response, chunks)

    return AgentRespones(
        scenario=validate_ai_response.get("scenario", "UNKNOWN"),
        output_language=validate_ai_response.get("output_language", "unknown"),
        ai_message=validate_ai_response.get("ai_message", ""),
        confident=validate_ai_response.get("confident", "0")
    )



