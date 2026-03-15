# Grafo LangGraph

## AgentState

O estado compartilhado entre todos os nós é definido como um `TypedDict` em `graph/workflow.py`:

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]  # acumulador
    current_topic: str          # tópico da pesquisa (input do usuário)
    recommendations: List[dict] # produtos retornados pela SearchAPI
    content_plan: dict          # plano de conteúdo criado pelo ProductManager
    critic_feedback: str        # "approved" ou texto de feedback
    human_feedback: str         # "y" (aprovar) ou "n. <motivo>"
    ceo_strategy: str           # diretiva estratégica do CEO
    critic_attempts: int        # contador de loops de revisão
```

O campo `messages` usa `operator.add` como reducer — cada nó que retorna `messages` os acumula, nunca os substitui.

## Fluxo do grafo

```
[entrada]
    │
    ▼
  ceo ──────────────────────────────────────► portfolio
                                                  │
                                                  ▼
                                          product_manager ◄────────────────┐
                                                  │                        │
                                                  ▼                        │
                                               critic                      │
                                                  │                        │
                          ┌───────────────────────┤                        │
                          │ reprovado             │ aprovado               │
                          │ (attempts < 2)        │ (ou attempts >= 2)     │
                          │                       ▼                        │
                          │                     human ── interrupt aqui    │
                          │                       │                        │
                          │         ┌─────────────┤                        │
                          │         │ rejeitado   │ aprovado               │
                          │         └─────────────┼────────────────────────┘
                          └───────► product_mgr   ▼
                                               writer
                                                  │
                                                  ▼
                                               [END]
```

## Definição dos nós

### `ceo_node`
Lê `data/posts.json` para contexto de publicações existentes e chama `CEOAgent.define_strategy()`. Retorna `ceo_strategy` (diretiva editorial) e uma mensagem.

### `portfolio_node`
Chama `PortfolioManagerAgent.analyze_and_recommend()` e `search_products()` via SearchAPI. Retorna `recommendations` com os produtos encontrados (máx. 5 exibidos na mensagem).

### `product_manager_node`
Chama `ProductManagerAgent.create_plan()`, passando `topic`, `recommendations`, `critic_feedback`, `human_feedback` e `ceo_strategy`. Retorna `content_plan` com campos `topic`, `angle`, `target_audience` e `key_products`.

### `critic_node`
Consulta o `MemoryManager` para contexto de decisões passadas. Chama `CriticAgent.review_plan()`. Se reprovado, incrementa `critic_attempts` e retorna feedback detalhado. Se aprovado, retorna `critic_feedback = "approved"`.

### `human_node`
Nó de passagem — o LangGraph interrompe o grafo antes deste nó (via `interrupt_before=["human"]`). Quando retomado, lê `human_feedback` do estado (injetado pelo endpoint `POST /agent/feedback`) e gera uma mensagem de confirmação.

### `writer_node`
Chama `ProductManagerAgent.create_content()` para gerar o artigo. Enriquece cada produto com preços reais via `find_product_offers()`. Salva o artigo em `data/posts.json` e registra a decisão no `MemoryManager`.

## Lógica de roteamento

### `should_continue_critic(state)`

```python
MAX_CRITIC_ATTEMPTS = 2

def should_continue_critic(state):
    feedback = state.get("critic_feedback", "")
    attempts = state.get("critic_attempts", 0)
    if feedback == "approved" or attempts >= MAX_CRITIC_ATTEMPTS:
        return "human"
    return "product_manager"
```

### `should_continue_human(state)`

```python
def should_continue_human(state):
    if state["human_feedback"].lower().startswith("y"):
        return "writer"
    return "product_manager"
```

## Compilação

```python
checkpointer = MemorySaver()
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["human"]
)
```

O `MemorySaver` persiste o estado do grafo em memória, indexado pelo `thread_id` passado na configuração. Isso permite que o backend retome a execução após o feedback humano com `graph.astream(None, config)`.

## Execução em duas fases

O backend executa o grafo em duas chamadas a `graph.astream()`:

1. **Fase 1**: `astream(initial_state, config)` — executa até o interrupt antes do nó `human`
2. **Fase 2**: `astream(None, config)` — retoma a partir do checkpoint com o `human_feedback` já injetado no estado via `graph.update_state()`
