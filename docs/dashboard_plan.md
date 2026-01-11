# Agent Dashboard & Refinement Strategy

## 1. Refinement Loop (Quality Assurance)
To ensure the content meets the high standards for SEO and Conversion, we will introduce a **Critic Node** in the LangGraph.

### Workflow Update
1.  ... -> Product Manager (Draft Plan) -> **Critic**
2.  **Critic Node**:
    - Role: Acts as a Senior SEO Editor & Conversion Specialist.
    - Input: The Draft Content Plan.
    - Checks:
        - Is the title click-worthy?
        - Is the "Angle" unique?
        - Are the products truly "best" for the topic?
        - Does it follow the "High Credibility" guideline?
    - Output: `feedback` (Approve or Request Changes).
3.  **Conditional Edge**:
    - If `feedback` has changes -> Back to **Product Manager** to refine.
    - If `Approve` -> **Human** (Final Check).

## 2. Agent Dashboard (UI)
We will create a dedicated section in the Next.js app (`/admin`) to visualize the "Brain" of the operation.

### Features
*   **Live Feed**: Reads `logs/conversation_history.md` and displays it like a chat interface.
*   **Memory Bank**: Visualizes the "Strategic Decisions" stored in ChromaDB (we'll export them to a JSON for the UI to read).
*   **Drafts**: Shows content that is currently in the "Refinement Loop" or waiting for approval.

### Technical Implementation
*   **Data Sync**: The Python agents will write their state updates to `frontend/public/agent_state.json` in real-time.
*   **Next.js**: The Admin page will poll this JSON file to update the UI without needing a complex backend server for now.
