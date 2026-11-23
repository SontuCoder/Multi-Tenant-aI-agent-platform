from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import create_tables
import uvicorn
from api import knowledge_route, agent_route

@asynccontextmanager
async def startup(app: FastAPI):
    # create_tables()
    print("Starting Multi-Tenant RAG Platform...")
    yield

app = FastAPI(title="Multi-Tenant RAG Platform", lifespan=startup)

@app.get("/", status_code=200)
def health():
    return {
        "message": "all Ok buddy 🙃👍"
    }

app.include_router(knowledge_route)
app.include_router(agent_route)

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, host="127.0.0.1", reload=True)