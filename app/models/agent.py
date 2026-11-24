
from sqlmodel import SQLModel, Field
from pydantic import EmailStr

class MailData(SQLModel):
    subject: str
    body: str
    sender: EmailStr
    to: EmailStr


class AgentRequest(SQLModel):
    mail_data: MailData | None
    input_language: str
    output_language: str
    user_question: str
    user_prompt: str


class AgentRespones(SQLModel):
    scenario: str
    output_language: str
    ai_message: str
    confident: str
