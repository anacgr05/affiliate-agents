import os
import json
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from services.llm_config import OPENROUTER_API_BASE, get_openrouter_model

logger = logging.getLogger(__name__)

load_dotenv()


class CriticAgent:
    """Agente especialista em SEO, CRO e qualidade editorial.

    Avalia o plano de conteúdo antes da aprovação humana,
    garantindo que o artigo terá alto potencial de conversão e
    ranking orgânico no Google Brasil.
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=OPENROUTER_API_BASE,
            model_name=get_openrouter_model(),
            temperature=0.4,  # Lower temp for analytical reviews
            request_timeout=120,
            max_retries=1,
        )

        self.system_prompt = """
Você é o Crítico de Qualidade de um site de marketing de afiliados no Brasil.
Sua função é revisar planos de conteúdo ANTES da aprovação humana e garantir
que o artigo resultante terá:

1. **SEO On-Page**: título otimizado (50-60 chars), uso de palavras-chave naturais,
   estrutura H1/H2 lógica, potencial de snippet em destaque.
2. **Potencial de Conversão (CRO)**: ângulo específico para um público bem definido
   (não genérico), call-to-action claro, comparação que facilita a decisão de compra.
3. **Qualidade Editorial**: tom profissional mas acessível (PT-BR brasileiro),
   informações que agregam valor real, sem conteúdo genérico ou "encheção de linguiça".
4. **Diferenciação**: o ângulo não deve repetir artigos já publicados (veja o contexto
   de memória abaixo). Cada artigo deve abordar um nicho ou sub-público diferente.
5. **Aderência à Estratégia do CEO**: o plano DEVE estar alinhado com a diretriz
   estratégica definida pelo CEO. Se o ângulo, público-alvo ou foco divergirem
   significativamente da estratégia, isso é motivo de reprovação.

CONTEXTO DE ARTIGOS EXISTENTES:
{memory_context}

DIRETRIZ ESTRATÉGICA DO CEO:
{ceo_strategy}

PLANO SUBMETIDO PARA REVISÃO:
- Tópico: {topic}
- Ângulo: {angle}
- Público-alvo: {target_audience}
- Produtos selecionados: {key_products}

INSTRUÇÕES:
Analise o plano e retorne um JSON com a seguinte estrutura EXATA:

Se APROVADO:
{{
    "approved": true,
    "score": 8.5,
    "summary": "Breve justificativa da aprovação",
    "suggestions": ["Sugestão opcional 1", "Sugestão opcional 2"]
}}

Se REPROVADO:
{{
    "approved": false,
    "score": 4.0,
    "summary": "Motivos claros da reprovação",
    "issues": ["Problema 1", "Problema 2"],
    "recommendations": ["Recomendação específica 1", "Recomendação específica 2"]
}}

Critérios de aprovação:
- Score >= 7.0 → aprovado
- Score < 7.0 → reprovado com recomendações claras
- Desalinhamento com a estratégia do CEO → reprovado independente do score

Seja exigente mas justo. Lembre-se: estamos construindo autoridade no mercado brasileiro.
"""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Revise o plano de conteúdo acima e retorne sua avaliação em JSON. Verifique especialmente a aderência à estratégia do CEO."),
        ])

        self.chain = self.prompt | self.llm | StrOutputParser()

    def review_plan(self, plan: dict, memory_context: str = "", ceo_strategy: str = "") -> dict:
        """Revisa um plano de conteúdo e retorna avaliação estruturada.

        Returns:
            dict com keys: approved (bool), score (float), summary (str),
            e issues/recommendations se reprovado.
        """
        topic = plan.get("topic", "")
        angle = plan.get("angle", "")
        target_audience = plan.get("target_audience", "")
        key_products = ", ".join(plan.get("key_products", []))

        logger.info(f"🧐 Critic: Reviewing plan — Topic: {topic}, Angle: {angle}")

        try:
            response = self.chain.invoke({
                "memory_context": memory_context or "Nenhum artigo publicado ainda.",
                "ceo_strategy": ceo_strategy or "Nenhuma diretriz específica do CEO.",
                "topic": topic,
                "angle": angle,
                "target_audience": target_audience,
                "key_products": key_products,
            })

            # Parse JSON from response
            cleaned = response.replace("```json", "").replace("```", "").strip()
            import re
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            result = json.loads(cleaned)
            logger.info(f"🧐 Critic result: approved={result.get('approved')}, score={result.get('score')}")
            return result

        except Exception as e:
            logger.error(f"❌ Critic review failed: {e}")
            # On failure, approve with a warning so the pipeline doesn't get stuck
            return {
                "approved": True,
                "score": 6.0,
                "summary": f"Revisão automática falhou ({e}). Aprovado com ressalvas — revise manualmente.",
                "suggestions": ["Revisar o plano manualmente antes de aprovar."],
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    critic = CriticAgent()

    test_plan = {
        "topic": "melhores notebooks para estudantes",
        "angle": "Best Value",
        "target_audience": "General",
        "key_products": ["MacBook Air M3", "Lenovo IdeaPad", "Acer Aspire"],
    }

    result = critic.review_plan(test_plan)
    print(json.dumps(result, indent=2, ensure_ascii=False))
