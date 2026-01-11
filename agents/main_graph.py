import os
import json
import operator
from typing import Annotated, List, TypedDict, Union
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Import existing agents
from portfolio_manager import PortfolioManagerAgent
from product_manager import ProductManagerAgent
from memory import MemoryManager

# Load environment variables
load_dotenv()

# --- State Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    current_topic: str
    recommendations: List[dict]
    content_plan: dict
    critic_feedback: str
    human_feedback: str

# --- Nodes ---

def ceo_node(state: AgentState):
    """The CEO decides the strategy or delegates."""
    print("\n👔 CEO: Assessing strategy...")
    # For now, simple pass-through to Portfolio, but could use LLM to decide topic
    topic = state.get("current_topic")
    message = f"Strategic Directive: Analyze market for '{topic}' and identify high-potential products."
    return {
        "messages": [AIMessage(content=message)]
    }

def portfolio_node(state: AgentState):
    """Portfolio Manager searches and analyzes products."""
    print("\n💼 Portfolio Manager: Searching for products...")
    topic = state["current_topic"]
    
    pm_agent = PortfolioManagerAgent()
    recommendations = pm_agent.analyze_and_recommend(topic)
    
    # Check if we got valid JSON-like string or just text. 
    # For simplicity in this graph, we assume the agent returns text analysis 
    # but we also need the raw list for the next step.
    # We might need to refactor PortfolioManager to return structured data + analysis.
    # For now, let's re-use the search_products method directly to get data
    
    raw_products = pm_agent.search_products(topic)
    
    message = f"Market Analysis Complete. Found {len(raw_products)} products. Recommendation: {recommendations[:100]}..."
    
    return {
        "recommendations": raw_products, # Passing raw data for better processing
        "messages": [AIMessage(content=message)]
    }

def product_manager_node(state: AgentState):
    """Product Manager creates a content plan."""
    print("\n📝 Product Manager: Creating content plan...")
    topic = state["current_topic"]
    recommendations = state["recommendations"]
    
    # Check if there is critic feedback to address
    critic_feedback = state.get("critic_feedback", "")
    human_feedback = state.get("human_feedback", "")
    
    pm_agent = ProductManagerAgent()
    plan = pm_agent.create_plan(
        topic=topic,
        recommendations=recommendations,
        critic_feedback=critic_feedback,
        human_feedback=human_feedback
    )
    
    message = f"Proposed Content Plan:\n- Topic: {plan.get('topic')}\n- Angle: {plan.get('angle')}\n- Products: {len(plan.get('key_products', []))}"
    if critic_feedback:
        message += f"\n- Addressed Critic Feedback: {critic_feedback}"
    if human_feedback:
        message += f"\n- Addressed Human Feedback: {human_feedback}"
    
    return {
        "content_plan": plan,
        "messages": [AIMessage(content=message)]
    }

def critic_node(state: AgentState):
    """Critic reviews the plan for SEO and Conversion quality."""
    print("\n🧐 Critic: Reviewing plan...")
    plan = state["content_plan"]
    
    # Simple mock logic for the critic (in real life, use an LLM call here)
    # If the angle is generic, reject it once.
    
    if "Best Value" in plan["angle"] and not state.get("critic_feedback"):
        feedback = "The angle 'Best Value' is too generic. Please make it more specific to a user persona (e.g., 'Students', 'Pro Gamers')."
        message = f"Critic Feedback: {feedback}"
        return {
            "critic_feedback": feedback,
            "messages": [AIMessage(content=message)]
        }
    else:
        # Approve if already refined or good enough
        return {
            "critic_feedback": "approved",
            "messages": [AIMessage(content="Critic Approved.")]
        }

def human_node(state: AgentState):
    """Human review node.
    In API mode, this node runs AFTER the user has provided feedback via the API.
    The feedback should already be injected into the state.
    """
    print("\n👤 Human Node Running...")
    feedback = state.get("human_feedback", "")
    print(f"Human Feedback Processed: {feedback}")
    
    return {
        "messages": [HumanMessage(content=f"Human Feedback: {feedback}")]
    }

def writer_node(state: AgentState):
    """Generates the final content."""
    print("\n✍️ Writer: Generating full article...")
    topic = state["current_topic"]
    # We pass the raw products to the PM agent to write the full thing
    # Re-using the ProductManagerAgent's create_content method
    
    pm_agent = ProductManagerAgent()
    # We need to pass the "recommendations" string that the PM expects
    # Or just pass the raw list and let the prompt handle it.
    # The current PM agent expects a string of recommendations.
    
    # Let's format the raw products into a string summary
    products_summary = json.dumps(state["recommendations"][:5])
    
    article_data = pm_agent.create_content(topic, products_summary)
    
    if article_data:
        # Save to file
        output_dir = "../frontend/content"
        os.makedirs(output_dir, exist_ok=True)
        posts_file = os.path.join(output_dir, "posts.json")
        
        posts = []
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                try: posts = json.load(f)
                except: posts = []
        
        posts.append(article_data)
        with open(posts_file, "w") as f:
            json.dump(posts, f, indent=2)
            
        # --- SAVE TO MEMORY ---
        mem = MemoryManager()
        mem.add_decision(
            topic=topic,
            decision=f"Published article: {article_data.get('title')}",
            agent_role="Product Manager",
            rationale=f"Approved by Human. Angle: {state['content_plan'].get('angle')}"
        )
            
        return {"messages": [AIMessage(content=f"Content published: {article_data.get('title')}")]}
    else:
        return {"messages": [AIMessage(content="Failed to generate content.")]}

# --- Graph Construction ---

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
        "product_manager": "product_manager"
    }
)

workflow.add_conditional_edges(
    "human",
    should_continue_human,
    {
        "writer": "writer",
        "product_manager": "product_manager"
    }
)

workflow.add_edge("writer", END)

# Use MemorySaver to persist state between API calls
checkpointer = MemorySaver()

app = workflow.compile(checkpointer=checkpointer, interrupt_before=["human"])

# --- Logger ---
def log_conversation(messages):
    # Ensure directory exists
    os.makedirs("../logs", exist_ok=True)
    with open("../logs/conversation_history.md", "a") as f:
        for msg in messages:
            role = "🤖 AI" if isinstance(msg, AIMessage) else "👤 Human"
            f.write(f"\n\n**{role}**: {msg.content}\n")

# --- Main Execution (CLI Legacy Support) ---
if __name__ == "__main__":
    # This block is for testing via CLI if needed, but the API will use 'app' directly
    pass
