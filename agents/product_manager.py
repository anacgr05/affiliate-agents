import os
import json
import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from services.llm_config import OPENROUTER_API_BASE, get_openrouter_model, LLM_TIMEOUT_SHORT, LLM_TIMEOUT_LONG
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

from services.memory import MemoryManager

class ProductManagerAgent:
    def __init__(self):
        self.memory = MemoryManager()
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=OPENROUTER_API_BASE,
            model_name=get_openrouter_model(),
            temperature=0.7,
            request_timeout=LLM_TIMEOUT_LONG,  # create_content is the heaviest call (~38s)
            max_retries=0,
        )
        self.search_api_key = os.getenv("SEARCHAPI_KEY")

        self.system_prompt = """
        You are the Product Manager and Lead Content Strategist for a top-tier affiliate marketing site in Brazil.
        Your goal is to take raw product data and market analysis and turn it into a high-converting "Landing Page" style review.

        CONTEXT:
        - Current Year: 2026
        - Target Audience: Brazilian Consumers
        - Language: Portuguese (PT-BR)

        Instead of a single markdown file, you must output a STRUCTURED JSON object that drives a rich frontend layout.

        Your responsibilities:
        1. Create a "Hero" section with a strong headline and subtitle.
        2. Select the top products and create detailed cards for them (Pros, Cons, Verdict).
        3. Write a "Buying Guide" with clear steps.
        4. Create a "FAQ" section.
        5. IMPORTANT: If you see multiple offers for the SAME product from different stores in the input data, GROUP them into a single product entry and list all the links in the 'affiliate_links' array. This allows for price comparison.
        6. Generate a creative "image_prompt" for the hero section. The style should be "not too realistic, believable, illustrative style". It should depict the essence of the topic without text.

        CONSIDER PAST DECISIONS:
        {memory_context}

        Input: A topic and a list of recommended products with analysis.
        Output: A JSON object with the following EXACT structure:
        {{
          "slug": "url-slug",
          "title": "SEO Title",
          "excerpt": "Short summary for SEO/Home page",
          "hero": {{
            "title": "Main Headline",
            "subtitle": "Subheadline",
            "image_prompt": "A creative prompt for an AI image generator...",
            "image": "https://placehold.co/1200x600?text=Hero+Image"
          }},
          "products": [
            {{
              "name": "Product Name",
              "price": "Approx Price",
              "rating": 4.8,
              "pros": ["Pro 1", "Pro 2"],
              "cons": ["Con 1"],
              "verdict": "Best for...",
              "affiliate_links": [
                {{"store": "Amazon", "url": "https://...", "price": "R$ 100"}}
              ]
            }}
          ],
          "buying_guide": {{
            "steps": [
              {{"title": "Step Title", "content": "Step description..."}}
            ]
          }},
          "faq": [
            {{"question": "...", "answer": "..."}}
          ]
        }}
        """

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Topic: {topic}\n\nPortfolio Manager Recommendations: {recommendations}\n\nGenerate the full article content in JSON format.")
        ])

        self.chain = self.prompt | self.llm | StrOutputParser()

        # --- Plan Generation Chain ---
        self.plan_system_prompt = """
        You are the Product Manager. Create a content plan for a new article.

        Topic: {topic}
        Context/Memory: {memory_context}
        Critic Feedback to Address: {critic_feedback}
        Human Feedback to Address: {human_feedback}

        **CEO STRATEGIC DIRECTIVE (FOLLOW THIS!):**
        {ceo_strategy}

        Available Products: {products_summary}

        IMPORTANT: You MUST align your plan with the CEO's strategic directive above.
        The CEO has analyzed the market, portfolio gaps, and SEO opportunities.
        Your plan should reflect their recommended angle, target audience, and focus keywords.

        Return a JSON object with:
        - "topic": The topic
        - "target_audience": Who is this for? (align with CEO directive)
        - "key_products": List of top 3 product names selected from available products.
        - "angle": The specific angle (align with CEO's recommended angle)
        - "improvements_made": How you addressed the feedback.
        """

        self.plan_prompt = ChatPromptTemplate.from_messages([
            ("system", self.plan_system_prompt),
            ("user", "Create the content plan.")
        ])

        self.plan_chain = self.plan_prompt | self.llm | StrOutputParser()

    def create_plan(self, topic, recommendations, critic_feedback="", human_feedback="", ceo_strategy=""):
        logger.info(f"📝 Product Manager planning for: {topic}...")

        # Retrieve context
        context = self.memory.retrieve_relevant_context(topic)

        # Summarize products for the prompt
        products_summary = json.dumps(recommendations[:5], indent=2) if isinstance(recommendations, list) else str(recommendations)

        try:
            response = self.plan_chain.invoke({
                "topic": topic,
                "memory_context": context,
                "critic_feedback": critic_feedback,
                "human_feedback": human_feedback,
                "products_summary": products_summary,
                "ceo_strategy": ceo_strategy or "Nenhuma diretriz específica — use seu melhor julgamento.",
            })
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            logger.error(f"❌ Error generating plan: {e}")
            # Fallback plan if LLM fails
            return {
                "topic": topic,
                "target_audience": "General",
                "key_products": [],
                "angle": "Guide",
                "improvements_made": "Error in generation"
            }

    def create_content(self, topic, recommendations):
        logger.info(f"✍️ Product Manager writing content for: {topic}...")

        # Retrieve context
        context = self.memory.retrieve_relevant_context(topic)

        try:
            response = self.chain.invoke({
                "topic": topic,
                "recommendations": recommendations,
                "memory_context": context
            })
            # Clean up potential markdown code blocks
            cleaned_response = response.replace("```json", "").replace("```", "").strip()

            # Attempt to find the first '{' and last '}' to isolate JSON
            import re
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                cleaned_response = json_match.group(0)

            # Remove potential invalid control characters
            cleaned_response = "".join(c for c in cleaned_response if c >= ' ' or c == '\n' or c == '\r' or c == '\t')

            return json.loads(cleaned_response, strict=False)
        except Exception as e:
            logger.error(f"❌ Error generating content: {e}")
            logger.error(f"Raw response was: {response}...") # Print full response for debugging
            return None

    def find_product_offers(self, product_name):
        """Searches for specific offers for a product to populate affiliate links."""
        if not self.search_api_key:
            logger.warning("⚠️ No SearchAPI key found, skipping price enrichment.")
            return []

        query = f"{product_name} comprar brasil"
        url = "https://www.searchapi.io/api/v1/search"
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.search_api_key,
            "location": "Brazil",
            "google_domain": "google.com.br",
            "gl": "br",
            "hl": "pt"
        }

        try:
            logger.info(f"💰 Searching offers for: {product_name}...")
            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200:
                logger.error(f"❌ SearchAPI failed: {response.status_code} {response.text}")
                return []

            data = response.json()
            results = data.get("shopping_results", [])

            offers = []
            seen_stores = set()

            # Prioritize major retailers
            priority_stores = ["Amazon", "Mercado Livre", "Kabum", "Pichau", "Terabyte", "Magalu", "Casas Bahia"]

            for item in results:
                store = item.get("source")
                if not store:
                    continue

                # Simple normalization for deduping
                store_norm = store.lower().replace(" ", "")
                if store_norm in seen_stores:
                    continue

                # Create offer object
                offer = {
                    "store": store,
                    "price": item.get("price"),
                    "url": item.get("product_link"),
                    "title": item.get("title") # Optional, for debugging
                }

                offers.append(offer)
                seen_stores.add(store_norm)

                if len(offers) >= 5: # Limit to top 5 distinct stores
                    break

            return offers

        except Exception as e:
            logger.error(f"❌ Error finding offers for {product_name}: {e}")
            return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pm = ProductManagerAgent()
    logger.info("Product Manager Initialized.")
