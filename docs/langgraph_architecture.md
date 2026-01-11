# Multi-Agent Collaboration Strategy (LangGraph)

## Goal
Transform the linear script into a stateful, interactive multi-agent system where:
1.  Agents communicate via a shared state (chat history).
2.  The User can view the conversation (`conversation_history.md`).
3.  The User can intervene/approve decisions (Human-in-the-loop).

## Architecture: The "Affiliate Graph"

We will use **LangGraph** to define the workflow.

### Shared State (`AgentState`)
```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_step: str
    current_topic: str
    recommendations: List[dict]
    content_plan: dict
    human_feedback: str
```

### Nodes (Agents)
1.  **CEO Node**:
    - Input: User request or previous agent output.
    - Action: Decides the high-level strategy or delegates.
    - Output: Updates `messages` with instructions.
2.  **Portfolio Node**:
    - Input: Strategy/Topic.
    - Action: Uses SearchAPI to find products.
    - Output: Updates `recommendations` and `messages`.
3.  **Product Manager Node**:
    - Input: Recommendations.
    - Action: Creates a *Content Plan* (Title, Angle, Structure) - NOT the full content yet.
    - Output: Updates `content_plan` and `messages`.
4.  **Human Node (The User)**:
    - Input: The Content Plan.
    - Action: Pauses execution. Displays the plan. Asks for approval or feedback.
    - Output: `human_feedback` (Approve / Change request).
5.  **Writer Node** (formerly part of PM):
    - Input: Approved Plan.
    - Action: Generates the full Markdown content.
    - Output: Saves file and updates `messages`.

### Workflow (Edges)
1.  Start -> CEO
2.  CEO -> Portfolio
3.  Portfolio -> PM
4.  PM -> **Human** (Review Plan)
5.  **Human**:
    - If "Approve" -> Writer
    - If "Changes" -> PM (Regenerate Plan)
6.  Writer -> End

## Observability
*   **Console**: Real-time streaming of agent thoughts.
*   **`logs/conversation.md`**: Appends every message to a markdown file for persistent history.

## Tech Stack Updates
*   Add `langgraph` to `requirements.txt`.
