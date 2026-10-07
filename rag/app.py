from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import uvicorn

import config


FRONTEND_DIR = config.RAG_DIR / "frontend"

app = FastAPI(title="Disaster Response Intelligence Repo Hub")

# Mount static files (CSS, JS, Images)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=FRONTEND_DIR / "templates")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def asset_version():
    """
    Changes whenever script.js or style.css changes. Used as ?v=... on
    their URLs so browsers never keep running an old cached copy.
    """
    static = FRONTEND_DIR / "static"
    return str(int(max(
        (static / "js" / "script.js").stat().st_mtime,
        (static / "css" / "style.css").stat().st_mtime,
    )))


# Make browsers re-check the page and static files on every load
@app.middleware("http")
async def no_stale_frontend(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"asset_version": asset_version()},
    )


@app.get("/healthz")
def health():
    """Liveness check used by Docker. Reports whether the DB exists."""
    return {
        "status": "ok",
        "database_ready": (config.CHROMA_PATH / "chroma.sqlite3").exists(),
    }


# A plain "def" (not "async def") makes FastAPI run this in a worker
# thread, so the slow embedding + LLM work does not freeze the server
# for every other user while one question is being answered.
@app.post("/api/ask")
def ask_question(req: QuestionRequest):

    # Imported lazily so the web UI can start before the model and
    # database assets have been provisioned.
    from rag_api import get_rag_answer
    from retrieval import DatabaseNotReadyError

    try:
        return get_rag_answer(req.question)

    except DatabaseNotReadyError as error:
        return JSONResponse(status_code=503, content={"error": str(error)})

    except Exception as error:
        print(f"Error running RAG pipeline: {error!r}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error running RAG pipeline: {error}"},
        )


if __name__ == "__main__":
    print("Starting server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
