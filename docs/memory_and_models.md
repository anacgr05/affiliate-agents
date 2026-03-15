# Memória e Modelos

## LLM — OpenRouter

Todos os agentes usam a mesma configuração de cliente LLM definida em `services/llm_config.py`.

**Modelo padrão:** `stepfun/step-3.5-flash:free`

Para substituir, defina a variável de ambiente antes de iniciar o backend:

```bash
export OPENROUTER_MODEL="openai/gpt-4o-mini"
```

A URL base é `https://openrouter.ai/api/v1`. O formato da API é compatível com OpenAI.

### Timeouts por agente

Os timeouts foram calibrados a partir de medições reais com o tier gratuito do StepFun, com margem de 2x para absorver variância:

| Constante | Valor | Agentes |
|-----------|-------|---------|
| `LLM_TIMEOUT_SHORT` | 45s | ProductManager, Analyst |
| `LLM_TIMEOUT_MEDIUM` | 60s | CEO, Portfolio, Critic |
| `LLM_TIMEOUT_LONG` | 90s | Writer |

Tempos típicos observados:
- CEO: ~28s
- Portfolio (analyze): ~20s
- ProductManager: ~8s
- Critic: ~18s
- Writer: ~38s

---

## Memória de Longo Prazo — ChromaDB + HuggingFace

### MemoryManager (`services/memory.py`)

Singleton que encapsula o ChromaDB e o modelo de embeddings. A primeira instanciação carrega o modelo `all-MiniLM-L6-v2` (HuggingFace local), o que pode levar 10-30 segundos e bloqueia o GIL do Python.

**Preloading no startup:**

Para evitar que esse bloqueio ocorra durante uma requisição, o servidor inicializa o `MemoryManager` no lifespan da aplicação, em uma thread separada:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(MemoryManager)
    yield
```

Após o preload, todas as chamadas subsequentes retornam a instância já inicializada instantaneamente (padrão singleton com `_instance`).

### Armazenamento

```
memory_db/                  # diretório persistido em disco
└── chroma.sqlite3          # ChromaDB SQLite backend
```

Collection: `affiliate_decisions`

### Formato dos documentos

```
Topic: <tópico>
Decision: <decisão tomada>
Rationale: <justificativa>
```

Metadata armazenada: `topic`, `agent`, `timestamp`.

### Quando a memória é escrita

O nó `writer_node` salva uma decisão após a aprovação humana e a publicação do artigo:

```python
mem.add_decision(
    topic=topic,
    decision=f"Published article: {article_data.get('title')}",
    agent_role="Product Manager",
    rationale=f"Approved by Human. Angle: {content_plan.get('angle')}"
)
```

### Quando a memória é lida

- **Nó `critic_node`**: recupera contexto relevante para o plano atual (query = tópico do plano, `k=5`)
- **Endpoint `GET /agent/memory`**: recupera contexto com query fixa `"feedback decision rationale"`, `k=5`, com cache de 30 segundos

### Método de busca

```python
def retrieve_relevant_context(self, query: str, k: int = 3) -> str:
    results = self.vector_store.similarity_search(query, k=k)
    return "Relevant Past Decisions:\n" + "\n".join(
        f"- {doc.page_content}" for doc in results
    )
```

Usa similaridade de cosseno entre embeddings. Retorna string vazia se não houver documentos.

---

## Busca de Produtos — SearchAPI

Usada pelo `PortfolioManagerAgent` e pelo `ProductManagerAgent`. Realiza buscas no Google Shopping com foco no mercado brasileiro.

**Variável de ambiente:** `SEARCHAPI_KEY`

Os resultados retornam campos como `title`, `price`, `source`, `rating` e links de afiliado. O Writer enriquece cada produto do plano com preços em tempo real via `find_product_offers()`.

---

## Persistência de Artigos — `data/posts.json`

O Writer salva os artigos gerados em `data/posts.json` como um array JSON, fazendo append a cada nova execução. O arquivo é lido pelo endpoint `GET /agent/posts` e pelo `ceo_node` (para contextualizar publicações existentes).

Estrutura de cada artigo:
```json
{
  "title": "...",
  "slug": "...",
  "hero": { "image": "...", "image_prompt": "..." },
  "products": [
    {
      "name": "...",
      "price": "...",
      "affiliate_links": [...]
    }
  ]
}
```
