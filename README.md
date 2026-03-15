# Affiliate Agents

Sistema multi-agente para geração automatizada de conteúdo afiliado. Um pipeline LangGraph orquestra agentes especializados que pesquisam produtos, criam um plano de conteúdo, revisam a qualidade e escrevem o artigo final — com uma etapa de aprovação humana no meio do fluxo.

## Stack

| Camada | Tecnologias |
|--------|-------------|
| Backend | FastAPI, LangGraph, MemorySaver, ChromaDB, HuggingFace Embeddings |
| LLM | OpenRouter (padrão: `stepfun/step-3.5-flash:free`) |
| Busca de produtos | SearchAPI — Google Shopping, Brasil |
| Frontend | Next.js 16 App Router, Turbopack, React, Tailwind CSS, ReactMarkdown |
| Streaming | SSE via `graph.astream()` + `asyncio.Event` para pausa human-in-the-loop |

## Pré-requisitos

- Python 3.11+ com `venv`
- Node.js 20+
- Chaves de API:

```bash
export OPENROUTER_API_KEY="sk-or-..."
export SEARCHAPI_KEY="..."
```

Opcionalmente, substitua o modelo LLM:

```bash
export OPENROUTER_MODEL="openai/gpt-4o-mini"
```

## Instalação

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

## Execução

```bash
# Backend + frontend juntos (padrão)
./run.sh

# Apenas o backend na porta 8000
./run.sh backend

# Apenas o frontend na porta 3000
./run.sh frontend
```

O script aguarda o backend responder em `localhost:8000/agent/status` antes de iniciar o frontend. Acesse o dashboard em `http://localhost:3000/admin/dashboard`.

## Pipeline

```
CEO → Portfolio → ProductManager → Critic
                                      |
                        reprovado     |     aprovado (ou limite de 2 tentativas)
                     ┌────────────────┘
                     v                v
              ProductManager        Human  ← interrompido aqui até POST /agent/feedback
                                      |
                    rejeitado         |     aprovado
                 ┌────────────────────┘
                 v                        v
          ProductManager               Writer → END
```

## Estrutura do projeto

```
affiliate-agents/
├── backend/
│   └── server.py                          # FastAPI — endpoints, SSE, run store
├── graph/
│   ├── workflow.py                        # StateGraph + AgentState + roteamento
│   └── nodes.py                           # Funções de nó para cada agente
├── agents/
│   ├── ceo.py
│   ├── portfolio_manager.py
│   ├── product_manager.py
│   ├── critic.py
│   └── analyst.py
├── services/
│   ├── llm_config.py                      # Timeouts e modelo OpenRouter
│   └── memory.py                          # MemoryManager singleton (ChromaDB)
├── frontend/
│   └── app/
│       ├── admin/dashboard/page.tsx       # Dashboard principal
│       └── api/agent/[...path]/route.ts   # Proxy catch-all para o backend
├── data/
│   └── posts.json                         # Artigos gerados (persistência em arquivo)
├── memory_db/                             # ChromaDB persistido em disco
└── run.sh
```

## Documentação

- [Arquitetura geral](docs/architecture.md)
- [Grafo LangGraph — nós e estado](docs/langgraph_architecture.md)
- [Referência da API backend](docs/backend_implementation_plan.md)
- [Proxy e camada frontend](docs/ui_control_architecture.md)
- [Dashboard — funcionalidades](docs/dashboard_plan.md)
- [Memória e modelos LLM](docs/memory_and_models.md)
