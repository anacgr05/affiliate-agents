import os
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage

from agents.portfolio_manager import PortfolioManagerAgent
from agents.product_manager import ProductManagerAgent
from services.memory import MemoryManager
from services.image_gen import generate_hero_image

logger = logging.getLogger(__name__)


def ceo_node(state):
    """The CEO decides the strategy or delegates."""
    logger.info("👔 CEO: Assessing strategy...")
    topic = state.get("current_topic")
    message = f"Strategic Directive: Analyze market for '{topic}' and identify high-potential products."
    return {
        "messages": [AIMessage(content=message)]
    }


def portfolio_node(state):
    """Portfolio Manager searches and analyzes products."""
    logger.info("💼 Portfolio Manager: Searching for products...")
    topic = state["current_topic"]

    pm_agent = PortfolioManagerAgent()
    recommendations = pm_agent.analyze_and_recommend(topic)

    raw_products = pm_agent.search_products(topic)

    message = f"Market Analysis Complete. Found {len(raw_products)} products. Recommendation: {recommendations[:100]}..."

    return {
        "recommendations": raw_products,
        "messages": [AIMessage(content=message)]
    }


def product_manager_node(state):
    """Product Manager creates a content plan."""
    logger.info("📝 Product Manager: Creating content plan...")
    topic = state["current_topic"]
    recommendations = state["recommendations"]

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


def critic_node(state):
    """Critic reviews the plan for SEO and Conversion quality."""
    logger.info("🧐 Critic: Reviewing plan...")
    plan = state["content_plan"]

    if "Best Value" in plan["angle"] and not state.get("critic_feedback"):
        feedback = "The angle 'Best Value' is too generic. Please make it more specific to a user persona (e.g., 'Students', 'Pro Gamers')."
        message = f"Critic Feedback: {feedback}"
        return {
            "critic_feedback": feedback,
            "messages": [AIMessage(content=message)]
        }
    else:
        return {
            "critic_feedback": "approved",
            "messages": [AIMessage(content="Critic Approved.")]
        }


def human_node(state):
    """Human review node. Feedback should already be injected into the state."""
    logger.info("👤 Human Node Running...")
    feedback = state.get("human_feedback", "")
    logger.info(f"Human Feedback Processed: {feedback}")

    return {
        "messages": [HumanMessage(content=f"Human Feedback: {feedback}")]
    }


def writer_node(state):
    """Generates the final content with price enrichment and image generation."""
    logger.info("✍️ Writer: Generating full article...")
    topic = state["current_topic"]

    pm_agent = ProductManagerAgent()
    products_summary = json.dumps(state["recommendations"][:5])
    article_data = pm_agent.create_content(topic, products_summary)

    if article_data:
        # --- PRICE ENRICHMENT ---
        if "products" in article_data:
            logger.info("💰 Enriching product data with real-time prices...")
            for product in article_data["products"]:
                product_name = product.get("name")
                if product_name:
                    offers = pm_agent.find_product_offers(product_name)
                    if offers:
                        product["affiliate_links"] = offers
                        if offers[0].get("price"):
                            product["price"] = offers[0]["price"]
                        logger.info(f"✅ Enriched {product_name} with {len(offers)} offers.")
                    else:
                        logger.warning(f"⚠️ No offers found for {product_name}")

        # --- IMAGE GENERATION ---
        if "hero" in article_data and "image_prompt" in article_data["hero"]:
            prompt = article_data["hero"]["image_prompt"]
            image_url = generate_hero_image(prompt)
            article_data["hero"]["image"] = image_url
            logger.info(f"🖼️ Image attached to article: {image_url}")

        # --- SAVE TO FILE ---
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, "data")
        os.makedirs(output_dir, exist_ok=True)
        posts_file = os.path.join(output_dir, "posts.json")

        posts = []
        if os.path.exists(posts_file):
            with open(posts_file, "r") as f:
                try:
                    posts = json.load(f)
                except Exception:
                    posts = []

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
