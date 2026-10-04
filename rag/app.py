from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import asyncio
from rag_api import get_rag_answer

app = FastAPI()

# Mount static files (CSS, JS, Images)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="frontend/templates")

class QuestionRequest(BaseModel):
    question: str

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/ask")
async def ask_question(req: QuestionRequest):
    try:
        # Run the heavy RAG logic (Vector Search + Groq LLM)
        real_answer = get_rag_answer(req.question)
        return {"answer": real_answer}
    except Exception as e:
        return {"answer": f"Error running RAG pipeline: {e}"}

if __name__ == "__main__":
    print("Starting server on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
