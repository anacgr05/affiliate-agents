# Memory & Model Strategy

## 1. Long-term Memory Architecture (RAG)
To ensure agents learn from past decisions and maintain consistency, we will implement a **Retrieval Augmented Generation (RAG)** system using **ChromaDB**.

### Structure
We will store "Strategic Decisions" as documents in the vector database.
*   **Content**: The decision made (e.g., "Focus on 'Best Value' angle for Gaming Laptops").
*   **Metadata**:
    *   `agent`: Who made the decision (e.g., CEO, PM).
    *   `topic`: The context (e.g., "notebooks gamer").
    *   `rationale`: Why this decision was made.
    *   `timestamp`: When it happened.

### Workflow
1.  **Retrieval**: Before an agent acts, it queries the memory: *"What worked well for similar topics in the past?"*
2.  **Action**: The agent uses this context to generate a better response.
3.  **Storage**: After Human Approval, the final plan/decision is embedded and saved to ChromaDB.

## 2. Model Specialization
We will assign specific LLMs to agents based on their role's complexity.

| Agent | Role | Recommended Model | Reason |
| :--- | :--- | :--- | :--- |
| **CEO** | Strategy, High-level direction | `anthropic/claude-3.5-sonnet` | Superior reasoning and nuance for strategic decisions. |
| **Product Manager** | Content writing, SEO, User Psychology | `anthropic/claude-3.5-sonnet` | Best-in-class writing capability and "human-like" tone. |
| **Portfolio Manager** | Data analysis, Search processing | `google/gemini-2.0-flash-001` | Large context window, fast, and cost-effective for processing lots of data. |

## 3. Scalability
*   **ChromaDB**: Runs locally now but can be swapped for a hosted vector DB (Pinecone, Weaviate) easily.
*   **LangChain Abstractions**: We use standard interfaces, so swapping models or DBs is a configuration change.
