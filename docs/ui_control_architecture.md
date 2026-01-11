# UI-Driven Agent Architecture

## Goal
Move agent control from Terminal (`input()`) to the Next.js Dashboard.

## Architecture

### 1. Backend (FastAPI)
We will create a lightweight Python server (`backend/main.py`) to host the LangGraph.

*   **State Management**: The graph instance will be persistent in memory (or checkpointer).
*   **Endpoints**:
    *   `POST /agent/start`: Initiates the graph with a topic.
    *   `GET /agent/status`: Returns the current conversation history and "waiting" status.
    *   `POST /agent/feedback`: Accepts "Approve" or "Reject + Comment" from the UI to resume execution.

### 2. LangGraph Updates
*   Remove `input()` calls.
*   Use `interrupt_before=["human"]` feature of LangGraph (or simply have the human node return a "WAITING" state and exit, to be resumed later).
*   Actually, LangGraph's `checkpointer` is the best way to handle "Human-in-the-loop". We can pause execution at the human node and resume when the API is called.

### 3. Frontend Updates (`/admin/dashboard`)
*   **Start Button**: Input field to send the topic to `/agent/start`.
*   **Chat View**: Polls `/agent/status` to show messages.
*   **Action Area**: If status is "WAITING_FOR_APPROVAL", show the Plan and "Approve/Reject" buttons.

## Implementation Steps
1.  Install `fastapi` and `uvicorn`.
2.  Refactor `agents/main_graph.py` to be importable and controllable.
3.  Create `backend/server.py`.
4.  Update Next.js Dashboard.
