from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from graph.workflow import app as graph_app
import uuid
import threading
import asyncio
import os
import json
import logging
import io
import time
from contextlib import redirect_stdout

# --- Log Capture Setup ---
log_stream = io.StringIO()
logger = logging.getLogger("agent_server")
logger.setLevel(logging.INFO)

# Custom handler to capture logs to memory
class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []
        self.lock = threading.Lock()

    def emit(self, record):
        try:
            msg = self.format(record)
            with self.lock:
                self.logs.append(msg)
                if len(self.logs) > 200:
                    self.logs.pop(0)
        except Exception:
            self.handleError(record)

memory_handler = ListHandler()
memory_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

logging.getLogger("agent_server").addHandler(memory_handler)
logging.getLogger("agents").addHandler(memory_handler)
logging.getLogger("graph").addHandler(memory_handler)
logging.getLogger("services").addHandler(memory_handler)

from services.memory import MemoryManager
from agents.analyst import AnalystAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pipeline State Tracking ---
# This tracks which step of the pipeline we're currently on,
# so the frontend can show real-time progress even while the graph is running.

PIPELINE_STEPS = [
    {"id": "ceo", "label": "CEO definindo estratégia", "emoji": "👔"},
    {"id": "portfolio", "label": "Gestor de Portfólio pesquisando produtos", "emoji": "💼"},
    {"id": "product_manager", "label": "Gestor de Produto criando plano", "emoji": "📝"},
    {"id": "critic", "label": "Crítico revisando qualidade", "emoji": "🧐"},
    {"id": "human", "label": "Aguardando aprovação humana", "emoji": "👤"},
    {"id": "writer", "label": "Redator gerando artigo final", "emoji": "✍️"},
]

pipeline_state = {
    "is_running": False,
    "current_step": None,      # e.g. "ceo", "portfolio", etc.
    "steps_completed": [],      # list of step ids already done
    "started_at": None,
    "error": None,
}
pipeline_lock = threading.Lock()


def update_pipeline(step_id: str | None = None, running: bool = True, error: str | None = None, completed_step: str | None = None):
    with pipeline_lock:
        pipeline_state["is_running"] = running
        if step_id is not None:
            pipeline_state["current_step"] = step_id
        if error is not None:
            pipeline_state["error"] = error
        if completed_step:
            if completed_step not in pipeline_state["steps_completed"]:
                pipeline_state["steps_completed"].append(completed_step)


def reset_pipeline():
    with pipeline_lock:
        pipeline_state["is_running"] = False
        pipeline_state["current_step"] = None
        pipeline_state["steps_completed"] = []
        pipeline_state["started_at"] = None
        pipeline_state["error"] = None


# Store thread_id for the current session
current_thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": current_thread_id}}


class StartRequest(BaseModel):
    topic: str

class FeedbackRequest(BaseModel):
    approved: bool
    comments: str = ""


def _run_graph_in_background(initial_state, run_config):
    """Run the LangGraph pipeline in a background thread, tracking each step."""
    try:
        for event in graph_app.stream(initial_state, config=run_config):
            # event is a dict like {"ceo": {...}}, {"portfolio": {...}}, etc.
            for node_name in event:
                update_pipeline(completed_step=node_name)
                # Predict what's next based on the graph flow
                step_order = [s["id"] for s in PIPELINE_STEPS]
                current_idx = step_order.index(node_name) if node_name in step_order else -1
                if current_idx + 1 < len(step_order):
                    next_step = step_order[current_idx + 1]
                    update_pipeline(step_id=next_step)

        # Check if we stopped at human interrupt
        state_snapshot = graph_app.get_state(run_config)
        if state_snapshot.next and "human" in state_snapshot.next:
            update_pipeline(step_id="human", running=True)
        else:
            update_pipeline(running=False)

    except Exception as e:
        logger.error(f"❌ Erro no pipeline: {e}")
        update_pipeline(running=False, error=str(e))


@app.post("/agent/start")
def start_agent(req: StartRequest):
    global current_thread_id, config
    current_thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": current_thread_id}}

    initial_state = {
        "messages": [HumanMessage(content=f"Iniciar pesquisa sobre: {req.topic}", name="human")],
        "current_topic": req.topic,
        "recommendations": [],
        "content_plan": {},
        "human_feedback": ""
    }

    # Reset and start pipeline tracking
    reset_pipeline()
    with pipeline_lock:
        pipeline_state["is_running"] = True
        pipeline_state["started_at"] = time.time()
        pipeline_state["current_step"] = "ceo"

    # Run in background thread so the API stays responsive
    thread = threading.Thread(
        target=_run_graph_in_background,
        args=(initial_state, config),
        daemon=True,
    )
    thread.start()

    return {"status": "started", "thread_id": current_thread_id}


@app.get("/agent/status")
async def get_status():
    try:
        state_snapshot = graph_app.get_state(config)
        current_state = state_snapshot.values
        next_step = state_snapshot.next

        messages = []
        if "messages" in current_state:
            messages = [
                {
                    "role": m.type,
                    "name": getattr(m, "name", None) or m.type,
                    "content": m.content,
                }
                for m in current_state["messages"]
            ]

        # Determine status from both graph state and pipeline tracker
        with pipeline_lock:
            is_running = pipeline_state["is_running"]

        status = "IDLE"
        if next_step and "human" in next_step:
            status = "WAITING_FOR_APPROVAL"
        elif is_running:
            status = "PROCESSING"

        return {
            "status": status,
            "messages": messages,
            "plan": current_state.get("content_plan", {})
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/agent/pipeline")
async def get_pipeline():
    """Returns the current pipeline progress for real-time UI updates."""
    with pipeline_lock:
        elapsed = None
        if pipeline_state["started_at"]:
            elapsed = round(time.time() - pipeline_state["started_at"], 1)

        return {
            "is_running": pipeline_state["is_running"],
            "current_step": pipeline_state["current_step"],
            "steps_completed": list(pipeline_state["steps_completed"]),
            "steps": PIPELINE_STEPS,
            "elapsed_seconds": elapsed,
            "error": pipeline_state["error"],
        }


@app.post("/agent/feedback")
def submit_feedback(req: FeedbackRequest):
    feedback_str = "y" if req.approved else f"n. {req.comments}"

    graph_app.update_state(config, {"human_feedback": feedback_str})

    # Mark human as completed, predict next step
    update_pipeline(step_id="writer" if req.approved else "product_manager", running=True, completed_step="human")

    # Resume in background thread
    thread = threading.Thread(
        target=_run_graph_in_background,
        args=(None, config),
        daemon=True,
    )
    thread.start()

    return {"status": "resumed"}


@app.get("/agent/memory")
async def get_memory():
    try:
        mem = MemoryManager()
        context = mem.retrieve_relevant_context("feedback decision rationale", k=5)
        return {"memory": context}
    except Exception as e:
        return {"memory": f"Erro ao acessar memória: {str(e)}"}


@app.get("/agent/posts")
async def get_posts():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        posts_file = os.path.join(current_dir, "..", "data", "posts.json")

        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                posts = json.load(f)
            return {"posts": posts}
        else:
            return {"posts": []}
    except Exception as e:
        return {"posts": [], "error": str(e)}


@app.get("/agent/logs")
async def get_logs():
    with memory_handler.lock:
        return {"logs": list(memory_handler.logs)}


@app.post("/agent/analyze")
def analyze_portfolio():
    try:
        analyst = AnalystAgent()
        posts = []
        posts_file = os.path.join(os.path.dirname(__file__), "..", "data", "posts.json")
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                posts = json.load(f)

        recommendations = analyst.analyze_portfolio(posts)
        return recommendations
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
