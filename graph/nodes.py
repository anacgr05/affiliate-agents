import os
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage

from agents.ceo import CEOAgent
from agents.critic import CriticAgent
from agents.portfolio_manager import PortfolioManagerAgent
from agents.product_manager import ProductManagerAgent
from services.memory import MemoryManager

try:
    from services.image_gen import generate_hero_image
except Exception:
    generate_hero_image = None

logger = logging.getLogger(__name__)


def ceo_node(state):
    """CEO defines the editorial strategy before the pipeline executes."""
    topic = state.get("current_topic")

    existing_posts = []
    try:
        posts_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "posts.json"
        )
        if os.path.exists(posts_file):
            with open(posts_file, "r", encoding="utf-8") as f:
                existing_posts = json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ CEO could not load existing posts: {e}")

    ceo = CEOAgent()
    strategy = ceo.define_strategy(topic, existing_posts)

    return {
        "ceo_strategy": strategy,
        "messages": [AIMessage(content=f"**Diretiva Estratégica do CEO**\n\n{strategy}", name="ceo")],
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
        human_feedback=human_feedback,
        ceo_strategy=state.get("ceo_strategy", ""),
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
    """Critic reviews the plan for SEO and conversion quality using CriticAgent."""
    plan = state["content_plan"]
    ceo_strategy = state.get("ceo_strategy", "")

    memory_context = ""
    try:
        mem = MemoryManager()
        memory_context = mem.retrieve_relevant_context(plan.get("topic", ""), k=5)
    except Exception as e:
        logger.warning(f"⚠️ Critic could not load memory context: {e}")

    critic = CriticAgent()
    result = critic.review_plan(plan, memory_context=memory_context, ceo_strategy=ceo_strategy)

    # Sub-score line shown in every message (approved or not)
    scores_line = (
        f"SEO: **{result.seo_score}** · "
        f"CRO: **{result.cro_score}** · "
        f"Diferenciação: **{result.differentiation_score}** · "
        f"CEO: **{result.ceo_alignment_score}**"
    )

    if result.approved:
        suggestions_md = (
            "\n\n**Sugestões:**\n" + "\n".join(f"- {s}" for s in result.suggestions)
        ) if result.suggestions else ""
        message = (
            f"**Revisão Aprovada** ✅ (Score: {result.overall_score}/10)\n\n"
            f"{result.summary}\n\n"
            f"*{scores_line}*"
            f"{suggestions_md}"
        )
        return {
            "critic_feedback": "approved",
            "messages": [AIMessage(content=message, name="critic")],
        }
    else:
        attempts = state.get("critic_attempts", 0) + 1

        # Build dimension-level feedback string for product_manager_node
        dim_lines = []
        if result.seo_issues:
            dim_lines.append(f"SEO ({result.seo_score}/10): " + "; ".join(result.seo_issues))
        if result.cro_issues:
            dim_lines.append(f"CRO ({result.cro_score}/10): " + "; ".join(result.cro_issues))
        if result.differentiation_issues:
            dim_lines.append(f"Diferenciação ({result.differentiation_score}/10): " + "; ".join(result.differentiation_issues))
        if result.ceo_alignment_issues:
            dim_lines.append(f"CEO ({result.ceo_alignment_score}/10): " + "; ".join(result.ceo_alignment_issues))

        feedback_parts = [f"Score: {result.overall_score}/10 (mínimo > 8.0)", result.summary]
        if dim_lines:
            feedback_parts.append("Por dimensão: " + " | ".join(dim_lines))
        if result.recommendations:
            feedback_parts.append("Recomendações: " + "; ".join(result.recommendations))
        feedback = " || ".join(feedback_parts)

        # Markdown for dashboard
        all_issues = result.seo_issues + result.cro_issues + result.differentiation_issues + result.ceo_alignment_issues
        issues_md = (
            "\n\n**Problemas por dimensão:**\n" + "\n".join(f"- {i}" for i in all_issues)
        ) if all_issues else ""
        recs_md = (
            "\n\n**Recomendações para o Product Manager:**\n" + "\n".join(f"- {r}" for r in result.recommendations)
        ) if result.recommendations else ""
        message = (
            f"**Revisão Reprovada** ❌ (Score: {result.overall_score}/10 — mínimo > 8.0)\n\n"
            f"{result.summary}\n\n"
            f"*{scores_line}*"
            f"{issues_md}{recs_md}"
        )
        return {
            "critic_feedback": feedback,
            "critic_attempts": attempts,
            "messages": [AIMessage(content=message, name="critic")],
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

    try:
        pm_agent = ProductManagerAgent()
        products_summary = json.dumps(state["recommendations"][:5])
        article_data = pm_agent.create_content(topic, products_summary)

        if not article_data:
            logger.error("❌ ProductManager returned None - content generation failed")
            return {"messages": [AIMessage(content="**Erro:** Não foi possível gerar o conteúdo. Verifique os logs para mais detalhes.", name="writer")]}

        # --- PRICE ENRICHMENT ---
        if "products" in article_data:
            logger.info("💰 Enriching product data with real-time prices...")
            for product in article_data["products"]:
                product_name = product.get("name")
                if product_name:
                    try:
                        offers = pm_agent.find_product_offers(product_name)
                        if offers:
                            product["affiliate_links"] = offers
                            if offers[0].get("price"):
                                product["price"] = offers[0]["price"]
                            logger.info(f"✅ Enriched {product_name} with {len(offers)} offers.")
                        else:
                            logger.warning(f"⚠️ No offers found for {product_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to enrich {product_name}: {e}")

        # --- IMAGE GENERATION ---
        # TEMPORARIAMENTE DESABILITADO - focando na geração do artigo
        # TODO: Re-habilitar quando resolver timeout da API de imagem
        if "hero" in article_data and "image_prompt" in article_data["hero"]:
            # prompt = article_data["hero"]["image_prompt"]
            # image_url = generate_hero_image(prompt)
            # article_data["hero"]["image"] = image_url
            article_data["hero"]["image"] = "https://placehold.co/1200x600?text=Hero+Image"
            logger.info(f"🖼️ Using placeholder image (generation disabled)")

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
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load existing posts: {e}")
                    posts = []

        posts.append(article_data)
        with open(posts_file, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Article saved to {posts_file}")

        # --- SAVE TO MEMORY ---
        try:
            mem = MemoryManager()
            mem.add_decision(
                topic=topic,
                decision=f"Published article: {article_data.get('title')}",
                agent_role="Product Manager",
                rationale=f"Approved by Human. Angle: {state['content_plan'].get('angle')}"
            )
            logger.info("✅ Decision saved to memory")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save to memory: {e}")

        return {
            "messages": [
                AIMessage(
                    content=f"**Artigo publicado com sucesso!**\n\nTítulo: *{article_data.get('title')}*\n\nSlug: `{article_data.get('slug')}`",
                    name="writer"
                )
            ]
        }

    except Exception as e:
        logger.error(f"❌ Writer node failed: {e}", exc_info=True)
        return {
            "messages": [
                AIMessage(
                    content=f"**Erro crítico no Writer:** {str(e)}\n\nVerifique os logs do backend para mais detalhes.",
                    name="writer"
                )
            ]
        }
