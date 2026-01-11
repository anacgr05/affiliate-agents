# Backend Implementation Plan

## 1. Refactor `agents/main_graph.py`
We need to make the graph "pausable" and "resumable" without `input()`.
*   **Change**: Remove `input()` from `human_node`.
*   **Change**: `human_node` will now just return a state indicating "WAITING_FOR_APPROVAL".
*   **Change**: Use `interrupt_before=["human"]` in `app.compile()` isn't strictly necessary if we manage state manually, but we'll use a simple state flag for now to keep it compatible with the API.
*   **New Function**: `run_graph_step(input_data)` that runs until it hits the human node or finishes.

## 2. Create `backend/server.py`
A FastAPI app to manage the graph lifecycle.

### Endpoints
*   `POST /start`:
    *   Body: `{"topic": "..."}`
    *   Action: Initializes `AgentState`, runs graph until Human Node.
    *   Returns: `{"status": "running"}`
*   `GET /status`:
    *   Action: Returns the full list of messages and current status (e.g., "WAITING_FOR_HUMAN", "COMPLETED", "PROCESSING").
    *   Returns: `{"messages": [...], "status": "...", "pending_plan": {...}}`
*   `POST /feedback`:
    *   Body: `{"approved": boolean, "comments": "..."}`
    *   Action: Updates state with `human_feedback` and resumes graph execution.

## 3. Frontend Integration
*   Update `frontend/app/admin/dashboard/page.tsx` to use these endpoints.
*   Add "Start Research" input.
*   Add "Approve / Reject" buttons that appear when status is "WAITING_FOR_HUMAN".

## Verification
1.  Start backend: `uvicorn backend.server:app --reload`
2.  Start frontend: `npm run dev`
3.  Go to Dashboard, start a topic.
4.  Verify logs appear.
5.  Verify "Approve" button appears when plan is ready.
6.  Click Approve and verify post is generated.
