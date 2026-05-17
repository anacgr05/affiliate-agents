# Affiliate Agents

Pipeline multi-agente para geração automatizada de conteúdo afiliado com imagens hero geradas por IA.

## Overview

Um grafo LangGraph orquestra agentes especializados (CEO, Portfolio Manager, Product Manager, Critic, Writer) que pesquisam produtos no Google Shopping, criam um plano de conteúdo, revisam qualidade com scoring e escrevem o artigo final. O artigo é persistido em PostgreSQL e um worker Celery gera assincronamente a imagem hero via OpenRouter. O fluxo inclui uma etapa de aprovação humana antes da escrita.

## Quick Start

### Pré-requisitos

- Python 3.11+ com `venv`
- Node.js 20+
- Docker (ou OrbStack) para PostgreSQL e Redis
- Chaves de API:

```bash
export OPENROUTER_API_KEY="sk-or-..."   # LLM + geração de imagem
export SEARCHAPI_KEY="..."              # Google Shopping via SearchAPI
```

### Instalação

```bash
# 1. Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Frontend
cd frontend && npm install && cd ..
```

### Execução

```bash
# Backend + frontend + Docker + Celery (padrão)
./run.sh

# Só o backend (porta 8000)
./run.sh backend

# Só o frontend (porta 3000)
./run.sh frontend
```

`run.sh` sobe o docker-compose (PostgreSQL + Redis), inicializa o banco, inicia o worker Celery e aguarda o backend responder antes de subir o frontend.

Acesse em `http://localhost:3000`.

## Key Features

- **Pipeline multi-agente** — CEO → Portfolio → Product Manager → Critic (com loop de revisão) → Human approval → Writer
- **Geração de imagem hero assíncrona** — Worker Celery chama OpenRouter (`google/gemini-3.1-flash-image-preview`) em background; frontend recebe via SSE quando a imagem fica pronta
- **Persistência em PostgreSQL** — artigos e status de imagem salvos no banco; fallback para `posts.json`
- **Streaming SSE** — eventos de nó chegam em tempo real no dashboard; imagens notificam via stream separado por slug
- **Human-in-the-loop** — pipeline pausa antes do Writer e aguarda aprovação via `POST /agent/feedback`
- **Backfill CLI** — importa posts existentes do JSON para o banco e dispara geração de imagem retroativamente

## Components

### Backend

| Arquivo | Responsabilidade |
|---------|-----------------|
| `backend/server.py` | FastAPI — SSE, endpoints de posts, static files (`/images`) |
| `backend/database.py` | Modelo `Post` (SQLAlchemy async) e `AsyncSessionLocal` |
| `backend/celery_app.py` | Celery app com roteamento para `main-queue` |
| `backend/worker.py` | Task `generate_image_task` — gera, salva PNG, atualiza DB |
| `backend/init_db.py` | Cria tabelas no PostgreSQL na inicialização |
| `backend/backfill.py` | CLI: persiste `posts.json` no banco e dispara jobs de imagem |

### Agentes

| Agente | Papel |
|--------|-------|
| `agents/ceo.py` | Define estratégia e nicho do conteúdo |
| `agents/portfolio_manager.py` | Analisa portfólio e detecta lacunas |
| `agents/product_manager.py` | Pesquisa produtos via SearchAPI |
| `agents/critic.py` | Avalia plano com rubric scoring (Pydantic `CriticResult`) |
| `agents/analyst.py` | Analisa portfólio existente sob demanda |

### Serviços

| Arquivo | Responsabilidade |
|---------|-----------------|
| `services/image_generator.py` | OpenRouter chat/completions → PNG bytes; prefixo landscape 16:9; parser dual-format (OpenAI + Gemini) |
| `services/post_repository.py` | CRUD síncrono (psycopg2) para posts — upsert por slug, status de imagem |
| `services/llm_config.py` | Modelo e timeouts do OpenRouter |
| `services/memory.py` | MemoryManager singleton (ChromaDB + HuggingFace embeddings) |

### Frontend

| Rota | Descrição |
|------|-----------|
| `/` | Grid de posts com imagens hero reais do banco |
| `/reviews/[slug]` | Artigo completo — hero, produtos, guia de compra, FAQ accordion |
| `/admin/dashboard` | Dashboard do pipeline — inicia geração, acompanha SSE, aprova plano |
| `/api/agent/[...path]` | Proxy catch-all para o backend em `localhost:8000` |

## Pipeline

```
CEO → Portfolio → ProductManager → Critic
                                      │
                     reprovado        │      aprovado (ou ≥ 2 tentativas)
                  ┌──────────────────-┘
                  ▼                          ▼
           ProductManager                 Human  ◄── pausa até POST /agent/feedback
                                            │
                   rejeitado               │      aprovado
                ┌──────────────────────────┘
                ▼                                     ▼
         ProductManager                           Writer → PostgreSQL + Celery image job → END
```

## Infraestrutura

```yaml
# docker-compose.yml
PostgreSQL 15  →  porta 5432  →  banco affiliate_db
Redis 7        →  porta 6379  →  broker + backend Celery
```

## Variáveis de Ambiente

| Variável | Obrigatória | Padrão | Descrição |
|----------|:-----------:|--------|-----------|
| `OPENROUTER_API_KEY` | ✅ | — | Chave OpenRouter (LLM + imagem) |
| `SEARCHAPI_KEY` | ✅ | — | Chave SearchAPI (Google Shopping) |
| `OPENROUTER_MODEL` | — | `z-ai/glm-5-turbo` | Modelo LLM para os agentes |
| `OPENROUTER_IMAGE_MODEL` | — | `google/gemini-3.1-flash-image-preview` | Modelo de geração de imagem |
| `DATABASE_URL` | — | `postgresql+asyncpg://affiliate_user:affiliate_password@localhost:5432/affiliate_db` | URL async do PostgreSQL |
| `DATABASE_URL_SYNC` | — | `postgresql+psycopg2://...` | URL sync (worker + repository) |
| `BACKEND_URL` | — | `http://localhost:8000` | URL base para URLs públicas de imagem |

## Estrutura do Projeto

```
affiliate-agents/
├── backend/
│   ├── server.py
│   ├── database.py
│   ├── celery_app.py
│   ├── worker.py
│   ├── init_db.py
│   └── backfill.py
├── graph/
│   ├── workflow.py
│   └── nodes.py
├── agents/
│   ├── ceo.py
│   ├── portfolio_manager.py
│   ├── product_manager.py
│   ├── critic.py
│   └── analyst.py
├── services/
│   ├── image_generator.py
│   ├── post_repository.py
│   ├── llm_config.py
│   └── memory.py
├── frontend/
│   └── app/
│       ├── page.tsx
│       ├── reviews/[slug]/page.tsx
│       ├── admin/dashboard/page.tsx
│       └── api/agent/[...path]/route.ts
├── data/
│   └── images/              # PNGs gerados pelo worker
├── docker-compose.yml
└── run.sh
```

## Documentação

- [Arquitetura geral](docs/architecture.md)
- [Grafo LangGraph — nós e estado](docs/langgraph_architecture.md)
- [Referência da API backend](docs/backend_implementation_plan.md)
- [Proxy e camada frontend](docs/ui_control_architecture.md)
- [Dashboard — funcionalidades](docs/dashboard_plan.md)
- [Memória e modelos LLM](docs/memory_and_models.md)
