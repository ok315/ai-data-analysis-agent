from fastapi import FastAPI
from pydantic import BaseModel
from agent import ask_agent_with_retry
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")

class QuestionRequest(BaseModel):
    question: str

@app.post("/ask")
def ask(request: QuestionRequest):
    answer, plan, attempts = ask_agent_with_retry(request.question)
    return {
        "question": request.question,
        "plan": plan,
        "answer": str(answer),
        "attempts": attempts
    }