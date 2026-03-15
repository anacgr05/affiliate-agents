import os
import json
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import logging
from services.llm_config import OPENROUTER_API_BASE, get_openrouter_model, LLM_TIMEOUT_SHORT

logger = logging.getLogger(__name__)

load_dotenv()

class AnalystAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=OPENROUTER_API_BASE,
            model_name=get_openrouter_model(),
            temperature=0.7,
            request_timeout=LLM_TIMEOUT_SHORT,
            max_retries=0,
        )

        self.system_prompt = """
        You are the Lead Data Analyst for an affiliate marketing site in Brazil.
        Your goal is to analyze the current content portfolio and identify GAPS and OPPORTUNITIES for new content.

        CONTEXT:
        - Current Year: 2026
        - Target Audience: Brazilian Consumers
        - Language: Portuguese (PT-BR)

        You should look for:
        1. Missing categories (e.g., we have headphones, but no microphones).
        2. Complementary products (e.g., we have cameras, we need lenses).
        3. Trending topics in tech/home for 2026.

        Input: A list of existing article titles/slugs.
        Output: A JSON object with a list of 3 recommended new topics.

        Example Output:
        {{
            "recommendations": [
                {{"topic": "Melhores Monitores 4K para Jogos em 2026", "reason": "Complementar aos reviews de mouse gamer"}},
                {{"topic": "Top 5 Cafeteiras Inteligentes do Momento", "reason": "Tendência de casa inteligente"}}
            ]
        }}
        """

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Current Content Portfolio: {portfolio}\n\nSuggest 3 new high-potential topics.")
        ])

        self.chain = self.prompt | self.llm | StrOutputParser()

    def analyze_portfolio(self, posts: list[dict]) -> dict:
        """Analyze portfolio gaps and suggest new topics.

        Handles empty portfolios gracefully.
        """
        logger.info(f"📈 Analyst Agent: Analyzing content portfolio ({len(posts)} posts)...")

        if not posts:
            portfolio_summary = (
                "O portfólio está VAZIO — nenhum artigo publicado ainda. "
                "Sugira 3 tópicos iniciais de alto potencial de conversão para "
                "um novo site de afiliados brasileiro focado em tecnologia e casa."
            )
        else:
            portfolio_summary = "\n".join(
                [f"- {p.get('title', 'Unknown')} ({p.get('slug', '')})" for p in posts]
            )

        response = None
        try:
            response = self.chain.invoke({"portfolio": portfolio_summary})

            # Robust JSON extraction
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                cleaned_response = json_match.group(0)

            return json.loads(cleaned_response)
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio: {e}")
            if response:
                logger.error(f"Raw response: {response[:500]}")
            return {"recommendations": []}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyst = AnalystAgent()
    logger.info("Analyst Agent Initialized.")
