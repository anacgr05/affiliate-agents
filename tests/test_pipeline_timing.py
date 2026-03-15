"""
Timing test do pipeline completo — roda cada agente em sequência com um tópico real
e imprime o tempo de cada etapa. Útil para calibrar timeouts.

Uso:
    PYTHONPATH=. python tests/test_pipeline_timing.py [tópico]

Exemplo:
    PYTHONPATH=. python tests/test_pipeline_timing.py "melhores fones bluetooth 2026"
"""
import sys
import time
import json
import logging

logging.basicConfig(level=logging.WARNING)  # silencia logs dos agentes durante o teste

TOPIC = sys.argv[1] if len(sys.argv) > 1 else "melhores teclados mecânicos 2026"
SEP = "─" * 60


def step(label: str):
    """Context-manager simples para medir tempo de uma etapa."""
    class _T:
        def __enter__(self):
            print(f"\n🔄  {label}...", flush=True)
            self.t0 = time.perf_counter()
            return self

        def __exit__(self, *_):
            elapsed = time.perf_counter() - self.t0
            status = "✅" if _ == (None, None, None) else "❌"
            print(f"{status}  {label}: {elapsed:.1f}s", flush=True)
            self.elapsed = elapsed

    return _T()


print(f"\n{SEP}")
print(f"Pipeline Timing Test")
print(f"Tópico: {TOPIC}")
print(SEP)

# ── 1. CEO ──────────────────────────────────────────────────────────────────
with step("CEO — define_strategy") as t_ceo:
    from agents.ceo import CEOAgent
    ceo = CEOAgent()
    strategy = ceo.define_strategy(TOPIC, existing_posts=[])

print(f"   Estratégia (primeiros 200 chars): {strategy[:200].strip()}...")

# ── 2. Portfolio Manager ─────────────────────────────────────────────────────
with step("Portfolio — search_products") as t_portfolio:
    from agents.portfolio_manager import PortfolioManagerAgent
    pm = PortfolioManagerAgent()
    products = pm.search_products(TOPIC)

print(f"   Produtos encontrados: {len(products)}")

with step("Portfolio — analyze_and_recommend") as t_recommend:
    recommendations = pm.analyze_and_recommend(TOPIC)

print(f"   Recomendação (primeiros 200 chars): {str(recommendations)[:200]}...")

# ── 3. Product Manager ───────────────────────────────────────────────────────
with step("Product Manager — create_plan") as t_plan:
    from agents.product_manager import ProductManagerAgent
    ppm = ProductManagerAgent()
    plan = ppm.create_plan(
        topic=TOPIC,
        recommendations=products[:5],
        ceo_strategy=strategy,
    )

print(f"   Ângulo: {plan.get('angle')}")
print(f"   Público: {plan.get('target_audience')}")
print(f"   Produtos: {plan.get('key_products', [])[:3]}")

# ── 4. Critic ────────────────────────────────────────────────────────────────
with step("Critic — review_plan") as t_critic:
    from agents.critic import CriticAgent
    critic = CriticAgent()
    review = critic.review_plan(plan, ceo_strategy=strategy)

print(f"   Aprovado: {review.get('approved')}  |  Score: {review.get('score')}")
print(f"   Resumo: {review.get('summary', '')[:200]}")

# ── 5. Product Manager — create_content ─────────────────────────────────────
with step("Writer (ProductManager) — create_content") as t_content:
    products_summary = json.dumps(products[:3])
    content = ppm.create_content(TOPIC, products_summary)

title = content.get("title", "N/A") if content else "FALHOU"
print(f"   Título: {title}")

# ── Resumo ───────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("RESUMO DE TEMPOS")
print(SEP)
steps = [
    ("CEO",               t_ceo.elapsed),
    ("Portfolio search",  t_portfolio.elapsed),
    ("Portfolio analyze", t_recommend.elapsed),
    ("Product Manager",   t_plan.elapsed),
    ("Critic",            t_critic.elapsed),
    ("Writer",            t_content.elapsed),
]
total = sum(s[1] for s in steps)
for name, elapsed in steps:
    bar = "█" * int(elapsed / total * 30)
    print(f"  {name:<22} {elapsed:6.1f}s  {bar}")
print(f"  {'TOTAL':<22} {total:6.1f}s")
print(SEP)
print()
