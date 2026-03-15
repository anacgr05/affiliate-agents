# Arquitetura do Sistema

## Visão geral

O sistema é composto por um backend FastAPI e um frontend Next.js que se comunicam via HTTP. O backend executa o grafo LangGraph em uma task asyncio, transmite eventos via SSE (Server-Sent Events) e persiste estado por meio do MemorySaver do LangGraph e do ChromaDB.

```
┌─────────────────────────────────────────────────────┐
│  Browser (Next.js App)                              │
│                                                     │
│  Dashboard ──── fetch /api/agent/* ──► Proxy Route  │
│      │                                    │         │
│      │   EventSource (SSE)                │ node:http│
│      └────────────────────────────────────┘         │
│             direto para :8000                       │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / SSE
                         ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI  :8000                                     │
│                                                     │
│  POST /agent/start ──► asyncio.create_task          │
│  GET  /agent/runs/{id}/stream ──► StreamingResponse │
│  POST /agent/feedback ──► asyncio.Event.set()       │
│  GET  /agent/status | /logs | /memory | /posts      │
│  POST /agent/analyze ──► AnalystAgent               │
│                                                     │
│  LangGraph StateGraph ──► graph.astream()           │
│    ceo → portfolio → product_manager → critic       │
│    → human (interrupt) → writer → END               │
│                                                     │
│  MemorySaver (checkpointer por thread_id)           │
│  ChromaDB + all-MiniLM-L6-v2                        │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  SearchAPI (Google Shopping) │ OpenRouter (LLM)     │
└─────────────────────────────────────────────────────┘
```

## Componentes principais

### Backend (`backend/server.py`)

FastAPI serve como camada de API. Cada execução do pipeline é identificada por um `run_id` (UUID) e mantida no dicionário em memória `_runs`. Cada entrada contém:

- `events` — buffer de eventos SSE (permite replay em reconexão)
- `queues` — conjunto de `asyncio.Queue` para assinantes SSE ativos
- `done` — flag de encerramento
- `feedback` — `asyncio.Event` que pausa a execução no nó `human`
- `config` — configuração LangGraph com `thread_id = run_id`

O pipeline é executado em uma task asyncio separada (`asyncio.create_task`), sem bloquear a resposta do endpoint `/agent/start`.

### Grafo LangGraph (`graph/workflow.py`, `graph/nodes.py`)

O `StateGraph` define o fluxo entre os nós. A compilação inclui `interrupt_before=["human"]`, o que faz o LangGraph pausar automaticamente antes do nó `human`. Quando o backend detecta `snapshot.next == ["human"]`, aguarda `asyncio.Event`. Após o feedback, o grafo é retomado com `graph.astream(None, config)`.

Nós síncronos são executados automaticamente pelo LangGraph no executor de threads padrão do asyncio — nenhuma bridge manual é necessária.

### Memória (`services/memory.py`)

`MemoryManager` é um singleton que carrega o modelo `all-MiniLM-L6-v2` uma única vez. O carregamento é feito na inicialização da aplicação via `lifespan` em uma thread separada (`asyncio.to_thread`) para evitar que o GIL bloqueie o event loop na primeira requisição. O ChromaDB é persistido em disco em `memory_db/`.

### Frontend (`frontend/`)

O dashboard (`app/admin/dashboard/page.tsx`) conecta um `EventSource` diretamente ao backend na porta 8000, contornando o Turbopack do Next.js, que armazenaria em buffer as respostas SSE e só as entregaria após o encerramento do stream.

Todas as outras chamadas HTTP passam pelo proxy catch-all (`app/api/agent/[...path]/route.ts`), que usa `node:http` com `agent: false` para criar um socket TCP novo a cada requisição — evitando erros `ECONNRESET` causados pelo pool de conexões do Node.js com o servidor Uvicorn.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `OPENROUTER_API_KEY` | Sim | Chave da API OpenRouter |
| `SEARCHAPI_KEY` | Sim | Chave da SearchAPI (Google Shopping) |
| `OPENROUTER_MODEL` | Não | Modelo LLM (padrão: `stepfun/step-3.5-flash:free`) |
| `TOKENIZERS_PARALLELISM` | Não | Definido como `false` automaticamente pelo servidor |

## Persistência

| Dado | Mecanismo |
|------|-----------|
| Estado do grafo entre fases | `MemorySaver` (in-memory, por `thread_id`) |
| Decisões dos agentes (RAG) | ChromaDB em `memory_db/` |
| Artigos gerados | `data/posts.json` (JSON append) |
| Logs do servidor | Ring buffer em memória (últimas 300 entradas) |
