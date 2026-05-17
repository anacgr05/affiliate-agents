import os
import re
import json
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field, ValidationError
from services.llm_config import OPENROUTER_API_BASE, get_openrouter_model, LLM_TIMEOUT_MEDIUM

logger = logging.getLogger(__name__)
load_dotenv()


class CriticResult(BaseModel):
    """Resultado estruturado da revisão do plano de conteúdo."""

    # Sub-scores por dimensão (0–10)
    seo_score: float = Field(ge=0.0, le=10.0, description="SEO: título (50-60 chars), keywords naturais, estrutura H1/H2, potencial de snippet")
    cro_score: float = Field(ge=0.0, le=10.0, description="CRO: ângulo específico para público definido, CTA claro, comparação que facilita decisão")
    differentiation_score: float = Field(ge=0.0, le=10.0, description="Diferenciação: ângulo não repete artigos existentes, sub-público único")
    ceo_alignment_score: float = Field(ge=0.0, le=10.0, description="Alinhamento com a diretriz estratégica do CEO")

    # Score final (média ponderada calculada pelo modelo)
    overall_score: float = Field(ge=0.0, le=10.0, description="Score ponderado: SEO×0.25 + CRO×0.35 + Diferenciação×0.20 + CEO×0.20")

    # Diagnóstico por dimensão (vazios quando a dimensão está ok)
    seo_issues: list[str] = Field(default_factory=list, description="Problemas específicos de SEO")
    cro_issues: list[str] = Field(default_factory=list, description="Problemas específicos de CRO/conversão")
    differentiation_issues: list[str] = Field(default_factory=list, description="Problemas de diferenciação ou repetição de ângulo")
    ceo_alignment_issues: list[str] = Field(default_factory=list, description="Divergências com a estratégia do CEO")

    # Recomendações acionáveis para o Product Manager (o que mudar)
    recommendations: list[str] = Field(default_factory=list, description="Ações concretas para o Product Manager corrigir o plano")

    # Sugestões opcionais mesmo após aprovação
    suggestions: list[str] = Field(default_factory=list, description="Melhorias opcionais quando o plano está aprovado")

    # Resumo geral (1-2 frases)
    summary: str = Field(description="Resumo da avaliação — motivo principal de aprovação ou reprovação")

    @property
    def approved(self) -> bool:
        """Aprovado apenas se overall > 8.0 E alinhamento com CEO >= 7.0."""
        return self.overall_score > 8.0 and self.ceo_alignment_score >= 7.0


class CriticAgent:
    """Agente especialista em SEO, CRO e qualidade editorial.

    Usa `with_structured_output` para retornar CriticResult diretamente —
    sem json.loads frágil. Sub-scores por dimensão guiam revisões cirúrgicas
    do Product Manager em vez de feedback genérico.
    """

    # Compact JSON schema injected into the prompt so any provider knows the format.
    _SCHEMA = json.dumps({
        "seo_score": 7.5,
        "cro_score": 6.0,
        "differentiation_score": 8.0,
        "ceo_alignment_score": 9.0,
        "overall_score": 7.4,
        "summary": "Justificativa em 1-2 frases",
        "seo_issues": ["problema SEO 1"],
        "cro_issues": ["problema CRO 1"],
        "differentiation_issues": [],
        "ceo_alignment_issues": [],
        "recommendations": ["Ação concreta para o Product Manager 1"],
        "suggestions": [],
    }, ensure_ascii=False, indent=2)

    def __init__(self):
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=OPENROUTER_API_BASE,
            model_name=get_openrouter_model(),
            temperature=0.4,
            request_timeout=LLM_TIMEOUT_MEDIUM,
            max_retries=0,
        )

        self.system_prompt = """
Você é o Crítico de Qualidade de um site de marketing de afiliados no Brasil.
Avalie o plano de conteúdo abaixo em 4 dimensões e preencha todos os campos da rubrica.

═══════════════════════════════════════════════════════════
CONTEXTO DE ARTIGOS EXISTENTES (para verificar diferenciação):
{memory_context}

DIRETRIZ ESTRATÉGICA DO CEO:
{ceo_strategy}

PLANO SUBMETIDO PARA REVISÃO:
- Tópico: {topic}
- Ângulo: {angle}
- Público-alvo: {target_audience}
- Produtos selecionados: {key_products}
═══════════════════════════════════════════════════════════

RUBRICA (score 0–10 por dimensão):

**SEO (seo_score)**
- 9-10: título 50-60 chars com keyword principal, H2s cobrem sub-intenções, alto potencial de featured snippet
- 7-8: título adequado, estrutura lógica, algum elemento faltando
- <7: título genérico ou muito longo, ausência de keyword, estrutura fraca

**CRO — Conversão (cro_score)**
- 9-10: ângulo ultra-específico (ex: "notebooks para estudantes de medicina com orçamento de R$3k"), CTA direto, comparação que elimina paralisia de decisão
- 7-8: ângulo definido, poderia ser mais específico
- <7: público genérico ("qualquer pessoa"), sem ângulo de decisão claro

**Diferenciação (differentiation_score)**
- 9-10: sub-público ou ângulo completamente novo em relação aos artigos existentes
- 7-8: nova perspectiva sobre tema já coberto
- <7: repete ângulo ou público de artigo já publicado

**Alinhamento CEO (ceo_alignment_score)**
- 9-10: ângulo e público-alvo perfeitamente alinhados com a diretriz estratégica
- 7-8: alinhado na essência, pequenas divergências aceitáveis
- <7: diverge do foco estratégico — REPROVAÇÃO AUTOMÁTICA independente do overall_score

**overall_score**: calcule como SEO×0.25 + CRO×0.35 + Diferenciação×0.20 + CEO×0.20
Aprovação: overall_score > 8.0 E ceo_alignment_score >= 7.0

Para cada dimensão com score < 8, preencha os campos de issues com problemas ESPECÍFICOS
e recommendations com correções ACIONÁVEIS para o Product Manager.
Seja exigente mas justo — estamos construindo autoridade no mercado brasileiro.

FORMATO DE SAÍDA — retorne SOMENTE o JSON abaixo, sem texto adicional:
{schema}
"""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Avalie o plano de conteúdo e retorne apenas o JSON preenchido."),
        ])

        self.chain = self.prompt | self.llm | StrOutputParser()

    def review_plan(self, plan: dict, memory_context: str = "", ceo_strategy: str = "") -> CriticResult:
        """Revisa um plano de conteúdo e retorna CriticResult tipado.

        Usa StrOutputParser + model_validate para compatibilidade universal com
        qualquer provider no OpenRouter (incluindo os que não suportam function
        calling ou json_schema response_format).

        Nunca lança exceção — em caso de falha retorna score 0 para que o
        pipeline reencaminhe ao Product Manager em vez de aprovar cegamente.
        """
        def product_to_text(product: str | dict | object) -> str:
            if isinstance(product, str):
                return product
            if isinstance(product, dict):
                return (
                    product.get("name")
                    or product.get("title")
                    or product.get("product_name")
                    or product.get("model")
                    or str(product)
                )
            return str(product)

        topic = plan.get("topic", "")
        angle = plan.get("angle", "")
        target_audience = plan.get("target_audience", "")
        raw_key_products: list[object] = plan.get("key_products", []) or []
        key_products = ", ".join(product_to_text(p) for p in raw_key_products)

        logger.info(f"🧐 Critic: Reviewing plan — Topic: {topic}, Angle: {angle}")

        try:
            raw: str = self.chain.invoke({
                "memory_context": memory_context or "Nenhum artigo publicado ainda.",
                "ceo_strategy": ceo_strategy or "Nenhuma diretriz específica do CEO.",
                "topic": topic,
                "angle": angle,
                "target_audience": target_audience,
                "key_products": key_products,
                "schema": self._SCHEMA,
            })

            # Extract JSON block from response (handles ```json ... ``` wrappers)
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(0)

            data = json.loads(cleaned)
            result = CriticResult.model_validate(data)

            logger.info(
                f"🧐 Critic result: approved={result.approved}, overall={result.overall_score} "
                f"(SEO={result.seo_score}, CRO={result.cro_score}, "
                f"Diff={result.differentiation_score}, CEO={result.ceo_alignment_score})"
            )
            return result

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"❌ Critic parse/validation failed: {e}\nRaw response: {raw[:300] if 'raw' in dir() else 'N/A'}")
            return CriticResult(
                seo_score=0.0, cro_score=0.0, differentiation_score=0.0, ceo_alignment_score=0.0,
                overall_score=0.0,
                summary=f"Falha ao interpretar resposta do crítico: {e}. Plano reenviado para revisão.",
                recommendations=["Verificar se o modelo está retornando JSON válido. Tentar novamente."],
            )
        except Exception as e:
            logger.error(f"❌ Critic LLM call failed: {e}")
            # Fail closed: score 0 força revisão pelo Product Manager.
            return CriticResult(
                seo_score=0.0, cro_score=0.0, differentiation_score=0.0, ceo_alignment_score=0.0,
                overall_score=0.0,
                summary=f"Revisão automática falhou: {e}. O plano deve ser revisado.",
                recommendations=["Investigar erro técnico na revisão. Reenviar o plano para nova tentativa."],
            )


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    critic = CriticAgent()

    test_plan = {
        "topic": "melhores notebooks para estudantes",
        "angle": "Best Value",
        "target_audience": "General",
        "key_products": ["MacBook Air M3", "Lenovo IdeaPad", "Acer Aspire"],
    }

    result = critic.review_plan(test_plan)
    print(f"\napproved={result.approved}")
    print(f"overall={result.overall_score} | SEO={result.seo_score} | CRO={result.cro_score} | Diff={result.differentiation_score} | CEO={result.ceo_alignment_score}")
    print(f"summary: {result.summary}")
    if result.recommendations:
        print("recommendations:", json.dumps(result.recommendations, ensure_ascii=False, indent=2))
