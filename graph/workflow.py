import os
import operator
from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.nodes import (
    ceo_node,
    portfolio_node,
    product_manager_node,
    critic_node,
    human_node,
    writer_node,
)


# --- State Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    current_topic: str
    recommendations: List[dict]
    content_plan: dict
    critic_feedback: str
    human_feedback: str
    ceo_strategy: str  # CEO's editorial strategy directive for downstream agents


# --- Routing Logic ---
def should_continue_critic(state: AgentState):
    feedback = state.get("critic_feedback", "")
    if feedback == "approved":
        return "human"
    else:
        return "product_manager"


def should_continue_human(state: AgentState):
    feedback = state["human_feedback"].lower()
    if feedback.startswith("y"):
        return "writer"
    else:
        return "product_manager"


# --- Graph Construction ---
workflow = StateGraph(AgentState)

workflow.add_node("ceo", ceo_node)
workflow.add_node("portfolio", portfolio_node)
workflow.add_node("product_manager", product_manager_node)
workflow.add_node("critic", critic_node)
workflow.add_node("human", human_node)
workflow.add_node("writer", writer_node)

workflow.set_entry_point("ceo")

workflow.add_edge("ceo", "portfolio")
workflow.add_edge("portfolio", "product_manager")
workflow.add_edge("product_manager", "critic")

workflow.add_conditional_edges(
    "critic",
    should_continue_critic,
    {
        "human": "human",
        "product_manager": "product_manager",
    },
)

workflow.add_conditional_edges(
    "human",
    should_continue_human,
    {
        "writer": "writer",
        "product_manager": "product_manager",
    },
)

workflow.add_edge("writer", END)

# Use MemorySaver to persist state between API calls
checkpointer = MemorySaver()

app = workflow.compile(checkpointer=checkpointer, interrupt_before=["human"])


# --- Utility ---
def log_conversation(messages):
    """Append messages to a conversation log file."""
    os.makedirs("logs", exist_ok=True)
    with open("logs/conversation_history.md", "a") as f:
        for msg in messages:
            role = "🤖 AI" if isinstance(msg, AIMessage) else "👤 Human"
            f.write(f"\n\n**{role}**: {msg.content}\n")
