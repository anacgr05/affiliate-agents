"""
Affiliate-Agents — Backend API

Streaming pattern:
  POST /agent/start        → creates run, returns run_id immediately
  GET  /agent/runs/{id}/stream → SSE: replays history + live node events
  POST /agent/feedback     → injects human feedback, unblocks pipeline

Pipeline execution uses graph.astream() directly — no manual thread bridges.
LangGraph handles sync nodes via its own run_in_executor internally.
Human-in-the-loop pause uses asyncio.Event (no polling, no WebSocket).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal, Post
from graph.workflow import app as graph_app
from sqlalchemy import select
import asyncio
import uuid
import json
import logging
import time
import os
import traceback
import threading

# ---------------------------------------------------------------------------
# Logging — in-memory ring buffer exposed via GET /agent/logs
# ---------------------------------------------------------------------------

class _RingHandler(logging.Handler):
    def __init__(self, max_entries: int = 300):
        super().__init__()
        self._buf: list[str] = []
        self._lock = threading.Lock()
        self._max = max_entries

    def emit(self, record):
        try:
            with self._lock:
                self._buf.append(self.format(record))
                if len(self._buf) > self._max:
                    self._buf = self._buf[-self._max:]
        except Exception:
            self.handleError(record)

    @property
    def entries(self) -> list[str]:
        with self._lock:
            return list(self._buf)


_ring = _RingHandler()
_ring.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

for _name in ("agent_server", "agents", "graph", "services"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.INFO)
    _log.addHandler(_ring)

logger = logging.getLogger("agent_server")

# ---------------------------------------------------------------------------
# Late imports (after log setup so their loggers inherit the handler)
# ---------------------------------------------------------------------------

from services.memory import MemoryManager  # noqa: E402
from agents.analyst import AnalystAgent    # noqa: E402

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# ---------------------------------------------------------------------------
# Startup — preload HuggingFace model before accepting requests
#
# MemoryManager loads 'all-MiniLM-L6-v2' on first instantiation.
# That load holds the Python GIL for 10-30 s, freezing the event loop
# mid-request. Doing it here, in a thread, avoids that entirely.
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("⏳ Preloading ChromaDB / HuggingFace embeddings…")
    try:
        await asyncio.to_thread(MemoryManager)
        logger.info("✅ MemoryManager ready.")
    except Exception as exc:
        logger.warning(f"⚠️  MemoryManager preload failed (continuing): {exc}")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_images_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "images")
os.makedirs(_images_dir, exist_ok=True)
app.mount("/images", StaticFiles(directory=_images_dir), name="images")

# ---------------------------------------------------------------------------
# Run store
#
# Each run:
#   events   – buffered SSE events (replayed on reconnect/refresh)
#   queues   – one asyncio.Queue per active SSE subscriber
#   done     – True once the pipeline ended (success or error)
#   feedback – asyncio.Event; .set() by POST /agent/feedback to resume
#   config   – LangGraph {"configurable": {"thread_id": run_id}}
# ---------------------------------------------------------------------------

_runs: dict[str, dict] = {}
_current_run_id: str | None = None  # latest run (for feedback routing)


def _new_run(run_id: str) -> dict:
    run = {
        "events":   [],
        "queues":   set(),
        "done":     False,
        "feedback": asyncio.Event(),
        "config":   {"configurable": {"thread_id": run_id}},
    }
    _runs[run_id] = run
    return run


async def _emit(run_id: str, event: dict | None) -> None:
    """Append event to history and push to all active SSE queues.
    None signals end-of-stream (closes subscriber connections)."""
    run = _runs.get(run_id)
    if not run:
        return
    if event is not None:
        run["events"].append(event)
    else:
        run["done"] = True
    for q in list(run["queues"]):
        await q.put(event)


def _messages_from(node_output: dict) -> list[dict]:
    return [
        {
            "role":    m.type,
            "name":    getattr(m, "name", None) or m.type,
            "content": m.content,
        }
        for m in node_output.get("messages", [])
    ]


async def _stream_phase(run_id: str, state_or_none, config: dict) -> None:
    """Run one phase of the graph and emit node_completed events.

    LangGraph's astream() runs sync nodes in the default thread-pool
    executor — no manual bridging needed. Each chunk arrives as soon
    as its node finishes.
    """
    async for chunk in graph_app.astream(state_or_none, config=config):
        for node_name, node_output in chunk.items():
            # LangGraph emits internal bookkeeping nodes (e.g. __interrupt__)
            # whose values are tuples, not state dicts — skip them.
            if node_name.startswith("__") or not isinstance(node_output, dict):
                continue
            logger.info(f"✅ Node completed: {node_name}")
            await _emit(run_id, {
                "type":     "node_completed",
                "node":     node_name,
                "messages": _messages_from(node_output),
                "plan":     node_output.get("content_plan") or {},
            })


async def _run_pipeline(run_id: str, initial_state: dict) -> None:
    """Full pipeline lifecycle.

    Phase 1: stream until LangGraph interrupt (before 'human' node).
    Pause:   emit waiting_approval, block on asyncio.Event.
    Phase 2: after feedback, resume and stream to completion.
    """
    run = _runs[run_id]
    config = run["config"]
    try:
        logger.info(f"▶️  Pipeline started — run_id={run_id}")
        await _emit(run_id, {
            "type":  "pipeline_started",
            "topic": initial_state.get("current_topic", ""),
        })

        # Phase 1 ─────────────────────────────────────────────────────
        await _stream_phase(run_id, initial_state, config)

        snapshot = await graph_app.aget_state(config)
        if snapshot.next and "human" in snapshot.next:
            logger.info("⏸️  Waiting for human feedback…")
            await _emit(run_id, {"type": "waiting_approval"})
            await run["feedback"].wait()   # released by POST /agent/feedback

            # Phase 2 ─────────────────────────────────────────────────
            await _stream_phase(run_id, None, config)

        await _emit(run_id, {"type": "pipeline_completed"})
        logger.info("🎉 Pipeline completed successfully!")

    except Exception as exc:
        logger.error(f"💥 Pipeline error: {exc}\n{traceback.format_exc()}")
        await _emit(run_id, {"type": "error", "message": str(exc)})

    finally:
        await _emit(run_id, None)   # sentinel → closes all SSE connections


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

@app.get("/agent/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request):
    """Server-Sent Events stream for one pipeline run.

    Replays buffered history first so page-refresh / reconnect works
    without losing events. Then streams live events from the queue.
    Keepalive comments sent every 25 s to prevent proxy timeouts.
    """
    run = _runs.setdefault(run_id, {
        "events": [], "queues": set(), "done": False,
        "feedback": asyncio.Event(),
        "config":   {"configurable": {"thread_id": run_id}},
    })
    queue: asyncio.Queue = asyncio.Queue()
    run["queues"].add(queue)

    async def generate():
        for evt in list(run["events"]):
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        if run["done"]:
            return
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    if event is None:
                        break
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            run["queues"].discard(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    topic: str


class FeedbackRequest(BaseModel):
    approved: bool
    comments: str = ""


@app.post("/agent/start")
async def start_agent(req: StartRequest):
    global _current_run_id
    run_id = str(uuid.uuid4())
    _new_run(run_id)
    _current_run_id = run_id

    initial_state = {
        "messages":        [HumanMessage(content=f"Iniciar pesquisa sobre: {req.topic}", name="human")],
        "current_topic":   req.topic,
        "recommendations": [],
        "content_plan":    {},
        "human_feedback":  "",
        "ceo_strategy":    "",
        "critic_attempts": 0,
    }

    asyncio.create_task(_run_pipeline(run_id, initial_state))
    logger.info(f"🚀 Pipeline started: {req.topic}")
    return {"status": "started", "run_id": run_id}


@app.post("/agent/feedback")
async def submit_feedback(req: FeedbackRequest):
    run = _runs.get(_current_run_id) if _current_run_id else None
    if not run or run["done"]:
        return {"status": "error", "detail": "no active run"}

    feedback_str = "y" if req.approved else f"n. {req.comments}"
    await asyncio.to_thread(graph_app.update_state, run["config"], {"human_feedback": feedback_str})
    logger.info(f"📨 Feedback received: {feedback_str}")

    run["feedback"].set()   # unblocks _run_pipeline → Phase 2
    return {"status": "resumed"}


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------

@app.get("/agent/status")
async def get_status():
    """Health-check + simple status for the run.sh readiness probe."""
    run = _runs.get(_current_run_id) if _current_run_id else None
    if not run or run["done"]:
        return {"status": "IDLE"}
    waiting = any(e.get("type") == "waiting_approval" for e in run["events"])
    if waiting and not run["feedback"].is_set():
        return {"status": "WAITING_FOR_APPROVAL"}
    return {"status": "PROCESSING"}


@app.get("/agent/logs")
def get_logs():
    return {"logs": _ring.entries}


_mem_cache: dict = {"value": "", "ts": 0.0}
_MEM_TTL = 30.0


# -- Memory/RAG (disabled by default — see services/memory.py) ----------------

@app.get("/agent/memory")
async def get_memory():
    now = time.time()
    if now - _mem_cache["ts"] < _MEM_TTL and _mem_cache["value"]:
        return {"memory": _mem_cache["value"]}
    try:
        def _query():
            return MemoryManager().retrieve_relevant_context("feedback decision rationale", k=5)
        result = await asyncio.to_thread(_query)
        _mem_cache["value"] = result or "Nenhuma memória registrada ainda."
        _mem_cache["ts"] = now
        return {"memory": _mem_cache["value"]}
    except Exception as exc:
        return {"memory": _mem_cache["value"] or f"Erro: {exc}"}


@app.get("/agent/posts")
def get_posts():
    """Return posts from PostgreSQL, falling back to posts.json if DB is unavailable."""
    try:
        from services.post_repository import get_all_posts
        db_posts = get_all_posts()
        if db_posts:
            return {"posts": db_posts}
    except Exception as exc:
        logger.warning(f"DB read failed, falling back to JSON: {exc}")

    try:
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "posts.json")
        if os.path.exists(f):
            with open(f) as fp:
                return {"posts": json.load(fp)}
        return {"posts": []}
    except Exception as exc:
        return {"posts": [], "error": str(exc)}


@app.get("/agent/posts/stream")
async def stream_post_image(slug: str, request: Request):
    """SSE stream de status de imagem para um post por slug (Story-04.03).

    Poll a cada 3s no banco até o status ser 'ready' ou 'image_failed'.
    Emite keepalive enquanto ainda 'image_pending'.
    """
    async def generate():
        while True:
            if await request.is_disconnected():
                break
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(Post).where(Post.slug == slug))
                    post = result.scalar_one_or_none()

                if post and post.image_status == "ready":
                    yield f"data: {json.dumps({'type': 'image_ready', 'url': post.image_url})}\n\n"
                    break
                elif post and post.image_status == "image_failed":
                    yield f"data: {json.dumps({'type': 'image_failed'})}\n\n"
                    break
            except Exception:
                pass
            yield ": keepalive\n\n"
            await asyncio.sleep(3.0)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/agent/posts/backfill")
async def backfill_posts():
    """Persist all posts from posts.json to PostgreSQL and dispatch image jobs for each."""
    def _run() -> dict:
        from services.post_repository import ensure_tables_exist, save_post

        ensure_tables_exist()

        posts_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "posts.json"
        )
        if not os.path.exists(posts_path):
            return {"dispatched": [], "failed": [], "message": "posts.json não encontrado"}

        with open(posts_path, encoding="utf-8") as fh:
            posts: list[dict] = json.load(fh)

        dispatched: list[dict] = []
        failed: list[dict] = []

        for post in posts:
            slug: str = post.get("slug", "?")
            prompt: str = (
                post.get("hero", {}).get("image_prompt")  # type: ignore[union-attr]
                or post.get("title", "")
            )
            try:
                post_id = save_post(post)
                celery_app.send_task(
                    "backend.worker.generate_image_task",
                    args=[post_id, prompt],
                )
                dispatched.append({"slug": slug, "post_id": post_id})
                logger.info(f"[backfill] ✅ {slug} → post_id={post_id}")
            except Exception as exc:
                failed.append({"slug": slug, "error": str(exc)})
                logger.warning(f"[backfill] ❌ {slug} → {exc}")

        return {"dispatched": dispatched, "failed": failed}

    return await asyncio.to_thread(_run)


@app.post("/agent/analyze")
async def analyze_portfolio():
    def _run():
        analyst = AnalystAgent()
        f = os.path.join(os.path.dirname(__file__), "..", "data", "posts.json")
        posts = json.load(open(f)) if os.path.exists(f) else []
        return analyst.analyze_portfolio(posts)
    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.error(f"❌ Analyze failed: {exc}")
        return {"error": str(exc), "recommendations": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
