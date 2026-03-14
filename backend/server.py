from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from graph.workflow import app as graph_app
import asyncio
import uuid
import threading
import traceback
import os
import json
import logging
import time
from typing import Set

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

from services.memory import MemoryManager
from agents.analyst import AnalystAgent

# Prevent HuggingFace tokenizers from spawning extra threads (reduces GIL contention)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# -- FastAPI App with lifespan --------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- WebSocket Connection Manager -----------------------------------------------

class ConnectionManager:
    """Manages WebSocket connections and broadcasts events to all connected clients."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active_connections.add(websocket)
        logger.info(f"🔌 WebSocket conectado. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            self.active_connections.discard(websocket)
        logger.info(f"🔌 WebSocket desconectado. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return

        disconnected = set()
        async with self.lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Erro ao enviar para WebSocket: {e}")
                disconnected.add(connection)

        if disconnected:
            async with self.lock:
                self.active_connections -= disconnected

manager = ConnectionManager()

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


# -- Background Graph Runner ---------------------------------------------------

async def _run_graph_in_background(initial_state, run_config):
    """Run the LangGraph pipeline and stream events via WebSocket."""
    try:
        logger.info("▶️  Background task started")
        await manager.broadcast({"type": "pipeline_started", "topic": initial_state["current_topic"]})

        # Run the blocking graph.stream() in a thread pool
        def _sync_stream():
            events = []
            for event in graph_app.stream(initial_state, config=run_config):
                events.append(event)
            return events

        events = await asyncio.to_thread(_sync_stream)

        for event in events:
            for node_name in event:
                logger.info(f"✅ Node concluído: {node_name}")
                update_pipeline(completed_step=node_name)

                # Broadcast node completion
                await manager.broadcast({
                    "type": "node_completed",
                    "node": node_name,
                    "timestamp": time.time()
                })

                idx = _STEP_ORDER.index(node_name) if node_name in _STEP_ORDER else -1
                if idx + 1 < len(_STEP_ORDER):
                    update_pipeline(step_id=_STEP_ORDER[idx + 1])

            # Update cached state after each node
            try:
                snapshot = await asyncio.to_thread(graph_app.get_state, run_config)
                _update_state_cache(snapshot)

                # Broadcast state update
                await manager.broadcast({
                    "type": "state_update",
                    "messages": [{"content": m.content, "name": getattr(m, 'name', 'system')}
                                for m in snapshot.values.get("messages", [])],
                    "plan": snapshot.values.get("content_plan", {}),
                    "next": list(snapshot.next) if snapshot.next else []
                })
            except Exception as e:
                logger.warning(f"Erro ao atualizar state cache: {e}")

        # ---- stream() finished normally ----
        logger.info("🏁 Stream concluído normalmente")
        snapshot = await asyncio.to_thread(graph_app.get_state, run_config)
        _update_state_cache(snapshot)
        _memory_cache["timestamp"] = 0.0  # invalidate memory cache

        if snapshot.next and "human" in snapshot.next:
            update_pipeline(step_id="human", running=True)
            await manager.broadcast({"type": "waiting_approval", "next": list(snapshot.next)})
        else:
            update_pipeline(running=False)
            await manager.broadcast({"type": "pipeline_completed"})
            logger.info("🎉 Pipeline finalizado com sucesso!")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"💥 Erro FATAL no pipeline: {e}\n{tb}")
        update_pipeline(running=False, error=str(e))
        await manager.broadcast({"type": "error", "message": str(e)})

    finally:
        # SAFETY NET
        with pipeline_lock:
            if pipeline_state["is_running"]:
                if not pipeline_state["error"]:
                    pipeline_state["error"] = "Pipeline encerrado inesperadamente."
                pipeline_state["is_running"] = False
                logger.warning("⚠️  Safety-net: pipeline forçado a parar")


# -- Endpoints -----------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time pipeline updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, wait for messages (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)

@app.post("/agent/start")
async def start_agent(req: StartRequest):
    global current_thread_id, config
    current_thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": current_thread_id}}

    initial_state = {
        "messages": [HumanMessage(content=f"Iniciar pesquisa sobre: {req.topic}", name="human")],
        "current_topic": req.topic,
        "recommendations": [],
        "content_plan": {},
        "human_feedback": "",
        "ceo_strategy": "",
    }

    reset_pipeline()
    with pipeline_lock:
        pipeline_state["is_running"] = True
        pipeline_state["started_at"] = time.time()
        pipeline_state["current_step"] = "ceo"

    # Use asyncio.create_task instead of threading.Thread for better compatibility
    asyncio.create_task(_run_graph_in_background(initial_state, config))
    logger.info(f"🚀 Pipeline iniciado para: {req.topic}")

    return {"status": "started", "thread_id": current_thread_id}


@app.get("/agent/status")
async def get_status():
    """Returns cached state — never touches graph_app."""
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
            status = "IDLE"  # show error via pipeline, but status returns to idle
        elif next_step and "human" in next_step:
            status = "WAITING_FOR_APPROVAL"
        elif is_running:
            status = "PROCESSING"

        return {"status": status, "messages": messages, "plan": plan}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/agent/pipeline")
async def get_pipeline():
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
async def submit_feedback(req: FeedbackRequest):
    feedback_str = "y" if req.approved else f"n. {req.comments}"

    await asyncio.to_thread(graph_app.update_state, config, {"human_feedback": feedback_str})
    logger.info(f"📨 Feedback recebido: {feedback_str}")

    update_pipeline(
        step_id="writer" if req.approved else "product_manager",
        running=True,
        completed_step="human",
    )

    asyncio.create_task(_run_graph_in_background(None, config))

    return {"status": "resumed"}


# -- Memory Cache --------------------------------------------------------------

_memory_cache = {"value": "", "timestamp": 0.0}
_MEMORY_CACHE_TTL = 30


@app.get("/agent/memory")
async def get_memory():
    """Async — ChromaDB query is offloaded to a thread so it never blocks the event loop."""
    try:
        with pipeline_lock:
            is_running = pipeline_state["is_running"]

        if is_running:
            return {"memory": _memory_cache["value"] or "Pipeline em execução…"}

        now = time.time()
        if now - _memory_cache["timestamp"] < _MEMORY_CACHE_TTL and _memory_cache["value"]:
            return {"memory": _memory_cache["value"]}

        # Offload ChromaDB query to thread
        def _query_memory():
            mem = MemoryManager()
            return mem.retrieve_relevant_context("feedback decision rationale", k=5)

        try:
            context = await asyncio.to_thread(_query_memory)
        except Exception as e:
            logger.warning(f"Erro ao acessar ChromaDB: {e}")
            return {"memory": _memory_cache["value"] or f"Erro: {e}"}

        _memory_cache["value"] = context
        _memory_cache["timestamp"] = now
        return {"memory": context}
    except Exception as e:
        return {"memory": _memory_cache["value"] or f"Erro: {e}"}


@app.get("/agent/posts")
def get_posts():
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
    with memory_handler.lock:
        return {"logs": list(memory_handler.logs)}


@app.post("/agent/analyze")
async def analyze_portfolio():
    """Run portfolio analysis in a thread to avoid blocking the event loop."""
    def _run_analysis():
        analyst = AnalystAgent()
        posts = []
        posts_file = os.path.join(os.path.dirname(__file__), "..", "data", "posts.json")
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                posts = json.load(f)
        return analyst.analyze_portfolio(posts)

    try:
        result = await asyncio.to_thread(_run_analysis)
        return result
    except Exception as e:
        logger.error(f"❌ Analyze endpoint failed: {e}")
        return {"error": str(e), "recommendations": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
