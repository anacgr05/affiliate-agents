import os
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage

from agents.portfolio_manager import PortfolioManagerAgent
from agents.product_manager import ProductManagerAgent
from services.image_gen import generate_hero_image

logger = logging.getLogger(__name__)


def ceo_node(state):
    """The CEO decides the strategy or delegates."""
    logger.info("👔 CEO: Assessing strategy...")
    topic = state.get("current_topic")
    message = (
        f"**Diretiva Estratégica**\n\n"
        f"Analisar o mercado para **'{topic}'** e identificar os produtos com maior potencial de conversão."
    )
    return {
        "messages": [AIMessage(content=message, name="ceo")]
    }


def portfolio_node(state):
    """Portfolio Manager searches and analyzes products."""
    logger.info("💼 Portfolio Manager: Searching for products...")
    topic = state["current_topic"]

    pm_agent = PortfolioManagerAgent()
    recommendations = pm_agent.analyze_and_recommend(topic)

    raw_products = pm_agent.search_products(topic)

    # Build a clean product summary for the message
    product_lines = []
    for p in raw_products[:5]:
        name = p.get("title", "Produto")
        price = p.get("price", "N/A")
        source = p.get("source", "")
        rating = p.get("rating", "")
        rating_str = f" — ⭐ {rating}" if rating else ""
        product_lines.append(f"- **{name}** — {price} ({source}){rating_str}")

    products_md = "\n".join(product_lines) if product_lines else "Nenhum produto encontrado."

    message = (
        f"**Análise de Mercado Concluída**\n\n"
        f"Encontrei **{len(raw_products)} produtos** para *\"{topic}\"*.\n\n"
        f"**Top 5 produtos:**\n{products_md}\n\n"
        f"**Recomendação do analista:**\n{recommendations[:300]}"
    )

    return {
        "recommendations": raw_products,
        "messages": [AIMessage(content=message, name="portfolio_manager")]
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

    key_products = plan.get("key_products", [])
    products_list = "\n".join([f"- {p}" for p in key_products]) if key_products else "Nenhum selecionado"

    message = (
        f"**Plano de Conteúdo Proposto**\n\n"
        f"- **Tópico:** {plan.get('topic', topic)}\n"
        f"- **Ângulo:** {plan.get('angle', 'N/A')}\n"
        f"- **Público-alvo:** {plan.get('target_audience', 'N/A')}\n"
        f"- **Produtos selecionados ({len(key_products)}):**\n{products_list}"
    )

    if critic_feedback and critic_feedback != "approved":
        message += f"\n\n> ✅ **Feedback do Crítico atendido:** {critic_feedback}"
    if human_feedback:
        message += f"\n\n> ✅ **Feedback Humano atendido:** {human_feedback}"

    return {
        "content_plan": plan,
        "messages": [AIMessage(content=message, name="product_manager")]
    }


def critic_node(state):
    """Critic reviews the plan for SEO and Conversion quality."""
    logger.info("🧐 Critic: Reviewing plan...")
    plan = state["content_plan"]

    if "Best Value" in plan["angle"] and not state.get("critic_feedback"):
        feedback = "O ângulo 'Best Value' é genérico demais. Torne-o mais específico para um público (ex: 'Estudantes', 'Gamers Profissionais')."
        message = (
            f"**Revisão Reprovada**\n\n"
            f"O plano precisa de ajustes antes de prosseguir.\n\n"
            f"> ⚠️ {feedback}"
        )
        return {
            "critic_feedback": feedback,
            "messages": [AIMessage(content=message, name="critic")]
        }
    else:
        message = (
            "**Revisão Aprovada** ✅\n\n"
            "O plano atende aos critérios de SEO e potencial de conversão. Aprovado para revisão humana."
        )
        return {
            "critic_feedback": "approved",
            "messages": [AIMessage(content=message, name="critic")]
        }


def human_node(state):
    """Human review node. Feedback should already be injected into the state."""
    logger.info("👤 Human Node Running...")
    feedback = state.get("human_feedback", "")
    logger.info(f"Human Feedback Processed: {feedback}")

    if feedback.lower().startswith("y"):
        message = "**Plano aprovado.** Prosseguindo para a geração do artigo."
    else:
        message = f"**Plano rejeitado.** Motivo: {feedback}"

    return {
        "messages": [HumanMessage(content=message, name="human")]
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
        try:
            from services.memory import MemoryManager
            mem = MemoryManager()
            mem.add_decision(
                topic=topic,
                decision=f"Published article: {article_data.get('title')}",
                agent_role="Product Manager",
                rationale=f"Approved by Human. Angle: {state['content_plan'].get('angle')}",
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to save to memory: {e}")

        return {"messages": [AIMessage(content=f"**Artigo publicado com sucesso!**\n\nTítulo: *{article_data.get('title')}*", name="writer")]}
    else:
        return {"messages": [AIMessage(content="**Erro:** Não foi possível gerar o conteúdo. Verifique os logs para mais detalhes.", name="writer")]}
