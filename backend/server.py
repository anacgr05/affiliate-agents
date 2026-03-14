from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from graph.workflow import app as graph_app
import uuid
import threading
import traceback
import os
import json
import logging
import time

# --- Log Capture Setup ---
logger = logging.getLogger("agent_server")
logger.setLevel(logging.INFO)


class ListHandler(logging.Handler):
    """Thread-safe handler that keeps the last N log messages in memory."""

    def __init__(self, max_entries: int = 300):
        super().__init__()
        self.logs: list[str] = []
        self._max = max_entries
        self.lock = threading.Lock()

    def emit(self, record):
        try:
            msg = self.format(record)
            with self.lock:
                self.logs.append(msg)
                if len(self.logs) > self._max:
                    self.logs = self.logs[-self._max:]
        except Exception:
            self.handleError(record)


memory_handler = ListHandler()
memory_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

for _name in ("agent_server", "agents", "graph", "services"):
    logging.getLogger(_name).addHandler(memory_handler)

from agents.analyst import AnalystAgent

# Prevent HuggingFace tokenizers from spawning extra threads (reduces GIL contention)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# -- FastAPI App --------------------------------------------------

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
    {"id": "ceo",             "label": "CEO",        "emoji": "👔"},
    {"id": "portfolio",       "label": "Portfólio",  "emoji": "💼"},
    {"id": "product_manager", "label": "Produto",    "emoji": "📝"},
    {"id": "critic",          "label": "Crítico",    "emoji": "🧐"},
    {"id": "human",           "label": "Aprovação",  "emoji": "👤"},
    {"id": "writer",          "label": "Redator",    "emoji": "✍️"},
]
_STEP_ORDER = [s["id"] for s in PIPELINE_STEPS]

pipeline_state = {
    "is_running": False,
    "current_step": None,
    "steps_completed": [],
    "started_at": None,
    "error": None,
}
pipeline_lock = threading.Lock()


# -- Cached state (updated by background thread; read by polling endpoints) ----

_last_state_cache = {
    "messages": [],
    "plan": {},
    "next": (),
}
_state_cache_lock = threading.Lock()


def _update_state_cache(state_snapshot):
    """Safely cache the graph state for fast reads from get_status."""
    try:
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
    except Exception as exc:
        logger.warning(f"_update_state_cache falhou: {exc}")


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


# -- Background Graph Runner (FULLY SYNCHRONOUS — runs in its own thread) ------

def _run_graph_in_background(initial_state, run_config):
    """Run the LangGraph pipeline in a dedicated thread.

    This function is fully synchronous — no asyncio, no event loop interaction.
    All state updates use threading.Lock which is safe from a background thread.
    """
    try:
        logger.info("▶️  Background task started")

        # Stream the graph (blocking, synchronous)
        for event in graph_app.stream(initial_state, config=run_config):
            for node_name in event:
                logger.info(f"✅ Node concluído: {node_name}")
                update_pipeline(completed_step=node_name)

                idx = _STEP_ORDER.index(node_name) if node_name in _STEP_ORDER else -1
                if idx + 1 < len(_STEP_ORDER):
                    update_pipeline(step_id=_STEP_ORDER[idx + 1])

            # Update cached state after each node
            try:
                snapshot = graph_app.get_state(run_config)
                _update_state_cache(snapshot)
            except Exception as e:
                logger.warning(f"Erro ao atualizar state cache: {e}")

        # ---- stream() finished normally ----
        logger.info("🏁 Stream concluído normalmente")
        try:
            snapshot = graph_app.get_state(run_config)
            _update_state_cache(snapshot)
        except Exception:
            pass

        if snapshot.next and "human" in snapshot.next:
            update_pipeline(step_id="human", running=True)
        else:
            update_pipeline(running=False)
            logger.info("🎉 Pipeline finalizado com sucesso!")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"💥 Erro FATAL no pipeline: {e}\n{tb}")
        update_pipeline(running=False, error=str(e))

    finally:
        # SAFETY NET
        with pipeline_lock:
            if pipeline_state["is_running"]:
                if not pipeline_state["error"]:
                    pipeline_state["error"] = "Pipeline encerrado inesperadamente."
                pipeline_state["is_running"] = False
                logger.warning("⚠️  Safety-net: pipeline forçado a parar")


# -- Endpoints -----------------------------------------------------------------
#
# DESIGN:
# - start_agent / submit_feedback: async def → response sent directly on event
#   loop, no threadpool handoff. The heavy graph work starts in a daemon thread
#   after a 2s delay (Timer), so the response is sent before any GIL contention.
# - get_status / get_pipeline / get_logs / get_posts: plain def → FastAPI runs
#   them in its thread pool. These use threading.Lock which would block the event
#   loop if they were async def.
# - get_memory / analyze_portfolio: plain def → blocking I/O (ChromaDB, LLM).


@app.post("/agent/start")
def start_agent(req: StartRequest):
    """Sync def — runs in FastAPI's thread pool.

    Timer(2s) delays the heavy graph work so the HTTP response is fully
    sent before any GIL-heavy computation begins.
    """
    global current_thread_id, config

    logger.info(f"🚀 Received start request for: {req.topic}")

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

    timer = threading.Timer(2.0, _run_graph_in_background, args=(initial_state, config))
    timer.daemon = True
    timer.start()

    return {"status": "started", "thread_id": current_thread_id}


@app.get("/agent/status")
def get_status():
    """Returns cached state — never touches graph_app. Sync def because it uses threading.Lock."""
    try:
        with pipeline_lock:
            is_running = pipeline_state["is_running"]
            error = pipeline_state["error"]

        with _state_cache_lock:
            messages = list(_last_state_cache["messages"])
            plan = dict(_last_state_cache["plan"]) if _last_state_cache["plan"] else {}
            next_step = _last_state_cache["next"]

        status = "IDLE"
        if error and not is_running:
            status = "IDLE"
        elif next_step and "human" in next_step:
            status = "WAITING_FOR_APPROVAL"
        elif is_running:
            status = "PROCESSING"

        return {"status": status, "messages": messages, "plan": plan}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/agent/pipeline")
def get_pipeline():
    """Sync def — uses threading.Lock."""
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
    """Sync def — graph_app.update_state is blocking, runs in thread pool."""
    feedback_str = "y" if req.approved else f"n. {req.comments}"

    graph_app.update_state(config, {"human_feedback": feedback_str})
    logger.info(f"📨 Feedback recebido: {feedback_str}")

    update_pipeline(
        step_id="writer" if req.approved else "product_manager",
        running=True,
        completed_step="human",
    )

    timer = threading.Timer(2.0, _run_graph_in_background, args=(None, config))
    timer.daemon = True
    timer.start()

    return {"status": "resumed"}


# -- Memory/RAG (disabled by default — see services/memory.py) ----------------

@app.get("/agent/memory")
def get_memory():
    """Memory/RAG — returns empty when ENABLE_MEMORY=0 (default)."""
    try:
        from services.memory import MemoryManager
        mem = MemoryManager()
        context = mem.retrieve_relevant_context("feedback decision rationale", k=5)
        return {"memory": context}
    except Exception as e:
        return {"memory": f"Erro ao acessar memória: {str(e)}"}


@app.get("/agent/posts")
def get_posts():
    """Sync def — file I/O runs in thread pool."""
    try:
        posts_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "posts.json")
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                posts = json.load(f)
            return {"posts": posts}
        return {"posts": []}
    except Exception as e:
        return {"posts": [], "error": str(e)}


@app.get("/agent/logs")
def get_logs():
    """Sync def — uses threading.Lock."""
    with memory_handler.lock:
        return {"logs": list(memory_handler.logs)}


@app.post("/agent/analyze")
def analyze_portfolio():
    """Run portfolio analysis (sync — runs in FastAPI thread pool)."""
    try:
        analyst = AnalystAgent()
        posts = []
        posts_file = os.path.join(os.path.dirname(__file__), "..", "data", "posts.json")
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                posts = json.load(f)
        return analyst.analyze_portfolio(posts)
    except Exception as e:
        logger.error(f"❌ Analyze endpoint failed: {e}")
        return {"error": str(e), "recommendations": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
