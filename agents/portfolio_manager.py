import os
import requests
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import logging
from services.llm_config import OPENROUTER_API_BASE, get_openrouter_model, LLM_TIMEOUT_MEDIUM

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class PortfolioManagerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=OPENROUTER_API_BASE,
            model_name=get_openrouter_model(),
            temperature=0.5,
            request_timeout=LLM_TIMEOUT_MEDIUM,
            max_retries=0,
        )
        self.search_api_key = os.getenv("SEARCHAPI_KEY")

        self.system_prompt = """
        You are the Portfolio Manager for a high-end affiliate marketing business in Brazil.
        Your role is to identify profitable products, analyze market trends, and select the best items to feature on our site.

        CONTEXT:
        - Current Year: 2026
        - Target Audience: Brazilian Consumers
        - Language: Portuguese (PT-BR)

        You have access to real-time market data via search tools.
        When analyzing products, consider:
        1. Price competitiveness.
        2. Review sentiment (look for high ratings but also detailed pros/cons).
        3. Market demand (trends).
        4. Affiliate commission potential (implied by product category and price).

        Output your analysis in a structured format suitable for the Product Manager to act upon.
        """

        self.analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Analyze these search results for '{query}' and recommend the top 3 products to feature. \n\nSearch Data: {search_data}")
        ])

        self.chain = self.analysis_prompt | self.llm | StrOutputParser()

    def search_products(self, query):
        """Searches for products using SearchAPI (Google Shopping engine)."""
        url = "https://www.searchapi.io/api/v1/search"
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.search_api_key,
            "location": "Brazil", # Defaulting to Brazil based on user language, can be parameterized
            "google_domain": "google.com.br",
            "gl": "br",
            "hl": "pt"
        }

        try:
            logger.info(f"🔎 Portfolio Manager searching for: {query}...")
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Extract relevant parts to save tokens
            results = data.get("shopping_results", [])[:10] # Top 10 results
            simplified_results = []
            for item in results:
                simplified_results.append({
                    "title": item.get("title"),
                    "price": item.get("price"),
                    "source": item.get("source"),
                    "rating": item.get("rating"),
                    "reviews": item.get("reviews"),
                    "link": item.get("product_link")
                })
            return simplified_results

        except Exception as e:
            logger.error(f"❌ Error searching products: {e}")
            return []

    def analyze_and_recommend(self, query):
        """Searches for products and generates an AI analysis."""
        search_data = self.search_products(query)

        if not search_data:
            return "No products found to analyze."

        logger.info(f"🧠 Portfolio Manager analyzing {len(search_data)} products...")
        response = self.chain.invoke({"query": query, "search_data": json.dumps(search_data, indent=2)})
        return response

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pm = PortfolioManagerAgent()
    logger.info("Portfolio Manager Initialized.")

    # Test interaction
    topic = "melhores notebooks gamer custo beneficio"
    recommendation = pm.analyze_and_recommend(topic)
    logger.info(f"\n📊 Analysis Result:\n{recommendation}")
