from fastapi import FastAPI
from database import create_tables
import uvicorn

app = FastAPI(title="Multi-Tenant RAG Platform")

@app.on_event("startup")
def startup():
    create_tables()


@app.get("/", status_code=200)
def health():
    return {
        "message": "all Ok buddy 🙃👍"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, host="127.0.0.1", reload=True)