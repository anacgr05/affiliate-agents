from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agents.main_graph import app as graph_app
import uuid
import threading
import asyncio

app = FastAPI()

# Store thread_id for the current session (simplification for single user)
current_thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": current_thread_id}}

class StartRequest(BaseModel):
    topic: str

class FeedbackRequest(BaseModel):
    approved: bool
    comments: str = ""

@app.post("/agent/start")
async def start_agent(req: StartRequest):
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
async def submit_feedback(req: FeedbackRequest):
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
