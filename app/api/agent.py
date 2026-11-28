from fastapi import APIRouter, status, Depends, HTTPException, Header, Query
from sqlmodel import Session
from uuid import UUID
from database import get_session
from models import AgentRespones, AgentRequest, APITokenCreated, APITokenResponse, APITokenCreate
from auth_services import get_current_user, CurrentAuth
from agent_services import search_similar_chunks, build_retrieval_text, build_retrieved_context, build_agent_prompt, execute_agent, validate_agent_result, create_new_agent_token, get_current_api_token, get_all_agent_tokens, delete_agent_token
from typing import Annotated



route = APIRouter(prefix="/api/agent", tags=["Agent"])

@route.post("/call", status_code=status.HTTP_200_OK, response_model=AgentRespones)
def get_agent_response( agent_request: AgentRequest, x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None, session: Session = Depends(get_session)):
    try:
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-API-Key header."
            )
    
        token = get_current_api_token(x_api_key, session)
        question = ""
        if agent_request.mail_data:
            question = build_retrieval_text(agent_request.mail_data.subject, agent_request.mail_data.body, agent_request.mail_data.sender, agent_request.mail_data.to, agent_request.user_question)
        else:
            question=agent_request.user_question
    
        chunks = search_similar_chunks(session, question, token.tenant_id, token.knowledge_base_id)
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
        validate_ai_response = validate_agent_result(agent_response, chunks)
    
        return AgentRespones(
            scenario=validate_ai_response.get("scenario", "UNKNOWN"),
            output_language=validate_ai_response.get("output_language", "unknown"),
            ai_message=validate_ai_response.get("ai_message", ""),
            confident=validate_ai_response.get("confident", "0")
        )
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to call agent."
        )
        

@route.post("/{tenant_id}/{knowledge_id}", status_code=status.HTTP_201_CREATED, response_model=APITokenCreated)
def create_token(tenant_id: UUID, knowledge_id:UUID, token_data: APITokenCreate, current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        return create_new_agent_token(current_auth.user, token_data.name, tenant_id, knowledge_id, session)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create API key."
        )

@route.get("/{tenant_id}/{knowledge_id}", status_code=status.HTTP_200_OK, response_model=list[APITokenResponse])
def get_tokens(tenant_id: UUID, knowledge_id:UUID, current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        return get_all_agent_tokens(current_auth.user, tenant_id, knowledge_id, session)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to get API keys."
        )


@route.delete("/{tenant_id}/{knowledge_id}", status_code=status.HTTP_200_OK)
def delete_tokens(tenant_id: UUID, knowledge_id:UUID, token_id: UUID = Query(), current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        delete_agent_token(current_auth.user, token_id, tenant_id, knowledge_id, session)
        return {
            "status" : "SUCCESS",
            "message": "Agent token delete successfully."
        }
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete API keys."
        )

