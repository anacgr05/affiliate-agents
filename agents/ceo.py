import os
import json
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from services.llm_config import OPENROUTER_API_BASE, get_openrouter_model, LLM_TIMEOUT_MEDIUM

from services.memory import MemoryManager

logger = logging.getLogger(__name__)

load_dotenv()


class CEOAgent:
    """Agente CEO — define a estratégia editorial antes do pipeline executar.

    Consulta a memória de decisões passadas e o portfólio existente
    para garantir que cada novo artigo tem um ângulo estratégico diferenciado.
    """

    def __init__(self):
        self.memory = MemoryManager()
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=OPENROUTER_API_BASE,
            model_name=get_openrouter_model(),
            temperature=0.6,
            request_timeout=LLM_TIMEOUT_MEDIUM,
            max_retries=0,
        )

        self.system_prompt = """
Você é o CEO e Diretor de Estratégia de um site de marketing de afiliados no Brasil.
Sua função é definir a DIRETRIZ ESTRATÉGICA para cada novo artigo antes que o time execute.

CONTEXTO:
- Mercado: Brasil
- Modelo de negócio: site de reviews de afiliados (comissão por clique/venda)
- Ano atual: 2026

ARTIGOS JÁ PUBLICADOS E DECISÕES PASSADAS:
{memory_context}

PORTFÓLIO EXISTENTE:
{portfolio_summary}

TÓPICO SOLICITADO PELO HUMANO: {topic}

SUA MISSÃO:
Analise o tópico pedido e dê uma diretriz estratégica que inclua:

1. **Validação**: Este tópico faz sentido para o nosso site? Tem potencial de conversão?
2. **Diferenciação**: Como este artigo deve se diferenciar do que já publicamos?
3. **Público-alvo sugerido**: Quem exatamente deveria ser o target deste artigo?
4. **Ângulo recomendado**: Qual o ângulo que maximiza conversão? (ex: "Melhor custo-benefício para universitários", "Top premium para profissionais")
5. **Palavras-chave foco**: 2-3 keywords principais para SEO em PT-BR
6. **Risco/Oportunidade**: Algum insight estratégico relevante?

Responda em Markdown, de forma concisa e acionável. Fale em português brasileiro.
Seja um CEO estratégico, não um escritor — dê DIRETRIZES, não conteúdo.
"""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Defina a estratégia para o tópico: {topic}"),
        ])

        self.chain = self.prompt | self.llm | StrOutputParser()

    def define_strategy(self, topic: str, existing_posts: list[dict] | None = None) -> str:
        """Gera diretriz estratégica para um tópico.

        Args:
            topic: O tópico pedido pelo humano.
            existing_posts: Lista de posts já publicados (do posts.json).

        Returns:
            String markdown com a diretriz estratégica.
        """
        # Get memory context
        try:
            memory_context = self.memory.retrieve_relevant_context(topic, k=5)
        except Exception:
            memory_context = ""

        # Build portfolio summary
        if existing_posts:
            portfolio_lines = [
                f"- {p.get('title', '???')} (slug: {p.get('slug', '???')})"
                for p in existing_posts
            ]
            portfolio_summary = "\n".join(portfolio_lines)
        else:
            portfolio_summary = "Nenhum artigo publicado ainda — este será o primeiro!"

        logger.info(f"👔 CEO: Defining strategy for '{topic}' (portfolio: {len(existing_posts or [])} articles)")

        try:
            response = self.chain.invoke({
                "topic": topic,
                "memory_context": memory_context or "Nenhuma decisão registrada ainda.",
                "portfolio_summary": portfolio_summary,
            })
            return response
        except Exception as e:
            logger.error(f"❌ CEO strategy generation failed: {e}")
            return (
                f"**Diretiva Estratégica**\n\n"
                f"Analisar o mercado para **'{topic}'** e identificar os produtos "
                f"com maior potencial de conversão.\n\n"
                f"*(Nota: análise estratégica avançada indisponível — {e})*"
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ceo = CEOAgent()
    result = ceo.define_strategy("melhores teclados mecânicos 2026")
    print(result)
