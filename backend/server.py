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
from contextlib import redirect_stdout

# --- Log Capture Setup ---
log_stream = io.StringIO()
# Configure logging to write to both stderr (console) and our stream
# Configure logging to write to both stderr (console) and our stream
# logging.basicConfig(level=logging.INFO) # Removing this as Uvicorn handles it
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
                if len(self.logs) > 100: # Keep last 100 logs
                    self.logs.pop(0)
        except Exception:
            self.handleError(record)

memory_handler = ListHandler()
memory_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

# Attach to specific loggers instead of root to avoid conflicts
# logging.getLogger("uvicorn").addHandler(memory_handler) # Removed to prevent conflicts
# logging.getLogger("uvicorn.access").addHandler(memory_handler) # Removed to prevent conflicts
logging.getLogger("agent_server").addHandler(memory_handler)
logging.getLogger("agents").addHandler(memory_handler) # Capture logs from agents package

# Also capture print statements by overriding print (simple hack for this scope)
# Print override removed to prevent deadlocks
# We will rely on standard logging or just stdout for now
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

# Store thread_id for the current session (simplification for single user)
current_thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": current_thread_id}}

class StartRequest(BaseModel):
    topic: str

class FeedbackRequest(BaseModel):
    approved: bool
    comments: str = ""

@app.post("/agent/start")
def start_agent(req: StartRequest):
    global current_thread_id, config
    current_thread_id = str(uuid.uuid4()) # New session
    config = {"configurable": {"thread_id": current_thread_id}}
    
    initial_state = {
        "messages": [HumanMessage(content=f"Start research on: {req.topic}")],
        "current_topic": req.topic,
        "recommendations": [],
        "content_plan": {},
        "human_feedback": ""
    }
    
    # Run until interrupt
    # We run this in a thread or just await if it was async, but graph.stream is sync generator usually unless using astream
    # For simplicity, we'll iterate until it stops
    try:
        for event in graph_app.stream(initial_state, config=config):
            pass # Just run until it pauses
        return {"status": "started", "thread_id": current_thread_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/agent/status")
async def get_status():
    try:
        # Get current state snapshot
        state_snapshot = graph_app.get_state(config)
        current_state = state_snapshot.values
        next_step = state_snapshot.next
        
        messages = []
        if "messages" in current_state:
            # Convert messages to string format for JSON
            messages = [{"role": m.type, "content": m.content} for m in current_state["messages"]]
            
        status = "IDLE"
        if next_step:
            if "human" in next_step:
                status = "WAITING_FOR_APPROVAL"
            else:
                status = "PROCESSING"
        
        return {
            "status": status,
            "messages": messages,
            "plan": current_state.get("content_plan", {})
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/agent/feedback")
def submit_feedback(req: FeedbackRequest):
    feedback_str = "y" if req.approved else f"n. {req.comments}"
    
    # Update state with feedback
    graph_app.update_state(config, {"human_feedback": feedback_str})
    
    # Resume execution
    try:
        # Pass None as input to resume
        for event in graph_app.stream(None, config=config):
            pass
        return {"status": "resumed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/agent/memory")
async def get_memory():
    try:
        mem = MemoryManager()
        # Retrieve all or recent memories. 
        # For now, let's just search for a generic term or get the last few if possible.
        # The current MemoryManager only has retrieve_relevant_context.
        # Let's assume we want to see everything relevant to "product".
        # Or better, we can add a method to MemoryManager to get recent items, 
        # but for now let's query broadly.
        # Retrieve relevant context. Using a broad query to get recent general feedback.
        context = mem.retrieve_relevant_context("feedback decision rationale", k=5)
        return {"memory": context}
    except Exception as e:
        return {"memory": f"Error accessing memory: {str(e)}"}

@app.get("/agent/posts")
async def get_posts():
    try:
        # Path to shared data directory
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
        # Read current posts
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
