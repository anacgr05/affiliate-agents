from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from graph.workflow import app as graph_app
import uuid
import threading
import os
import json
import logging
import io
import time

# --- Log Capture Setup ---
log_stream = io.StringIO()
logger = logging.getLogger("agent_server")
logger.setLevel(logging.INFO)


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs: list[str] = []
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
memory_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

logging.getLogger("agent_server").addHandler(memory_handler)
logging.getLogger("agents").addHandler(memory_handler)
logging.getLogger("graph").addHandler(memory_handler)
logging.getLogger("services").addHandler(memory_handler)

from services.memory import MemoryManager
from agents.analyst import AnalystAgent

# -- FastAPI App ---------------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Pipeline State Tracking ---------------------------------------------------

PIPELINE_STEPS = [
    {"id": "ceo",             "label": "CEO definindo estratégia",        "emoji": "👔"},
    {"id": "portfolio",       "label": "Gestor de Portfólio pesquisando", "emoji": "💼"},
    {"id": "product_manager", "label": "Gestor de Produto criando plano", "emoji": "📝"},
    {"id": "critic",          "label": "Crítico revisando qualidade",     "emoji": "��"},
    {"id": "human",           "label": "Aguardando aprovação humana",     "emoji": "👤"},
    {"id": "writer",          "label": "Redator gerando artigo final",    "emoji": "✍️"},
]

pipeline_state = {
    "is_running": False,
    "current_step": None,
    "steps_completed": [],
    "started_at": None,
    "error": None,
}
pipeline_lock = threading.Lock()


# -- Cached state from last completed run (updated by background thread) ------
# This avoids calling graph_app.get_state() while the graph is streaming,
# which would deadlock with graph_lock or block for minutes.
_last_state_cache = {
    "messages": [],
    "plan": {},
    "next": (),
}
_state_cache_lock = threading.Lock()


def _update_state_cache(state_snapshot):
    """Cache the graph state for fast reads from get_status."""
    with _state_cache_lock:
        current = state_snapshot.values
        _last_state_cache["next"] = state_snapshot.next or ()
        _last_state_cache["plan"] = current.get("content_plan", {})
        if "messages" in current:
            _last_state_cache["messages"] = [
                {
                    "role": m.type,
                    "name": getattr(m, "name", None) or m.type,
                    "content": m.content,
                }
                for m in current["messages"]
            ]


def update_pipeline(
    step_id: str | None = None,
    running: bool = True,
    error: str | None = None,
    completed_step: str | None = None,
):
    with pipeline_lock:
        pipeline_state["is_running"] = running
        if step_id is not None:
            pipeline_state["current_step"] = step_id
        if error is not None:
            pipeline_state["error"] = error
        if completed_step and completed_step not in pipeline_state["steps_completed"]:
            pipeline_state["steps_completed"].append(completed_step)


def reset_pipeline():
    with pipeline_lock:
        pipeline_state["is_running"] = False
        pipeline_state["current_step"] = None
        pipeline_state["steps_completed"] = []
        pipeline_state["started_at"] = None
        pipeline_state["error"] = None


# -- Session State -------------------------------------------------------------

current_thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": current_thread_id}}


class StartRequest(BaseModel):
    topic: str


class FeedbackRequest(BaseModel):
    approved: bool
    comments: str = ""


# -- Background Graph Runner ---------------------------------------------------

def _run_graph_in_background(initial_state, run_config):
    """Run the LangGraph pipeline in a background thread, tracking each step."""
    try:
        # stream() is long-running — do NOT hold a lock during it
        for event in graph_app.stream(initial_state, config=run_config):
            for node_name in event:
                update_pipeline(completed_step=node_name)
                step_order = [s["id"] for s in PIPELINE_STEPS]
                idx = step_order.index(node_name) if node_name in step_order else -1
                if idx + 1 < len(step_order):
                    update_pipeline(step_id=step_order[idx + 1])

            # Update cached state after each node so get_status can read it
            try:
                snapshot = graph_app.get_state(run_config)
                _update_state_cache(snapshot)
            except Exception:
                pass  # non-critical

        # Final state after stream completes
        snapshot = graph_app.get_state(run_config)
        _update_state_cache(snapshot)

        if snapshot.next and "human" in snapshot.next:
            update_pipeline(step_id="human", running=True)
        else:
            update_pipeline(running=False)

    except Exception as e:
        logger.error(f"Erro no pipeline: {e}")
        update_pipeline(running=False, error=str(e))


# -- Endpoints -----------------------------------------------------------------
#
# KEY DESIGN:
# Endpoints that touch graph_app or MemoryManager are plain `def` (sync).
# FastAPI runs sync `def` in an external thread-pool automatically,
# so they NEVER block the async event loop.  This prevents
# "socket hang up / ECONNRESET" errors from the Next.js proxy.
#
# Only truly lightweight endpoints (pipeline, logs) are `async def`.


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
        "human_feedback": "",
    }

    reset_pipeline()
    with pipeline_lock:
        pipeline_state["is_running"] = True
        pipeline_state["started_at"] = time.time()
        pipeline_state["current_step"] = "ceo"

    thread = threading.Thread(
        target=_run_graph_in_background,
        args=(initial_state, config),
        daemon=True,
    )
    thread.start()

    return {"status": "started", "thread_id": current_thread_id}


@app.get("/agent/status")
async def get_status():
    """Returns status from cached state — never blocks on graph_app."""
    try:
        with pipeline_lock:
            is_running = pipeline_state["is_running"]

        with _state_cache_lock:
            messages = list(_last_state_cache["messages"])
            plan = dict(_last_state_cache["plan"]) if _last_state_cache["plan"] else {}
            next_step = _last_state_cache["next"]

        status = "IDLE"
        if next_step and "human" in next_step:
            status = "WAITING_FOR_APPROVAL"
        elif is_running:
            status = "PROCESSING"

        return {"status": status, "messages": messages, "plan": plan}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/agent/pipeline")
async def get_pipeline():
    """Lightweight -- no blocking I/O, safe as async."""
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
    """Sync def → runs in thread-pool, won't block event loop."""
    feedback_str = "y" if req.approved else f"n. {req.comments}"

    graph_app.update_state(config, {"human_feedback": feedback_str})

    update_pipeline(
        step_id="writer" if req.approved else "product_manager",
        running=True,
        completed_step="human",
    )

    thread = threading.Thread(
        target=_run_graph_in_background,
        args=(None, config),
        daemon=True,
    )
    thread.start()

    return {"status": "resumed"}


@app.get("/agent/memory")
def get_memory():
    """Sync def -> runs in thread-pool (ChromaDB is blocking)."""
    try:
        mem = MemoryManager()
        context = mem.retrieve_relevant_context("feedback decision rationale", k=5)
        return {"memory": context}
    except Exception as e:
        return {"memory": f"Erro ao acessar memória: {str(e)}"}


@app.get("/agent/posts")
def get_posts():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        posts_file = os.path.join(current_dir, "..", "data", "posts.json")
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                posts = json.load(f)
            return {"posts": posts}
        return {"posts": []}
    except Exception as e:
        return {"posts": [], "error": str(e)}


@app.get("/agent/logs")
async def get_logs():
    """Lightweight -- just reads from memory list."""
    with memory_handler.lock:
        return {"logs": list(memory_handler.logs)}


@app.post("/agent/analyze")
def analyze_portfolio():
    """Sync def -> runs in thread-pool (LLM call is blocking)."""
    try:
        analyst = AnalystAgent()
        posts = []
        posts_file = os.path.join(os.path.dirname(__file__), "..", "data", "posts.json")
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                posts = json.load(f)
        return analyst.analyze_portfolio(posts)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
