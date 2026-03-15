# Referência da API Backend

Base URL: `http://localhost:8000`

---

## POST /agent/start

Inicia o pipeline para um tópico. Retorna `run_id` imediatamente; a execução ocorre em background.

**Request body:**
```json
{ "topic": "melhores mouses gamer 2026" }
```

**Response:**
```json
{ "status": "started", "run_id": "550e8400-e29b-41d4-a716-446655440000" }
```

Após receber o `run_id`, conecte um `EventSource` em `GET /agent/runs/{run_id}/stream` para acompanhar o progresso.

---

## GET /agent/runs/{run_id}/stream

Stream SSE de eventos para um pipeline em execução. Ao conectar, todos os eventos anteriores são reenviados (replay do buffer), permitindo reconexão sem perda de histórico. Após o replay, envia eventos ao vivo.

Um comentário de keepalive (`: keepalive`) é enviado a cada 25 segundos enquanto aguarda o próximo evento.

**Content-Type:** `text/event-stream`

### Tipos de evento

#### `pipeline_started`
```json
{ "type": "pipeline_started", "topic": "melhores mouses gamer 2026" }
```

#### `node_completed`
Emitido após cada nó do grafo concluir.
```json
{
  "type": "node_completed",
  "node": "product_manager",
  "messages": [
    { "role": "ai", "name": "product_manager", "content": "**Plano de Conteúdo...**" }
  ],
  "plan": {
    "topic": "...",
    "angle": "...",
    "target_audience": "...",
    "key_products": ["produto A", "produto B"]
  }
}
```
O campo `plan` está presente apenas quando o nó `product_manager` produz um `content_plan`. Para outros nós, é `{}`.

#### `waiting_approval`
```json
{ "type": "waiting_approval" }
```
Indica que o grafo foi interrompido antes do nó `human`. O frontend deve exibir o painel de aprovação. O pipeline permanece pausado até receber `POST /agent/feedback`.

#### `pipeline_completed`
```json
{ "type": "pipeline_completed" }
```

#### `error`
```json
{ "type": "error", "message": "descrição do erro" }
```

---

## POST /agent/feedback

Injeta o feedback humano e retoma o pipeline. Aplica ao run mais recente (`_current_run_id`).

**Request body:**
```json
{ "approved": true, "comments": "" }
```

Se `approved` for `false`, `comments` é incluído no feedback enviado ao `ProductManager` para revisão.

**Response:**
```json
{ "status": "resumed" }
```

Internamente: chama `graph.update_state()` com `human_feedback` e chama `asyncio.Event.set()` para desbloquear a fase 2 do pipeline.

---

## GET /agent/status

Retorna o estado atual do pipeline.

**Response:**
```json
{ "status": "IDLE" }
```

Valores possíveis:

| Status | Significado |
|--------|-------------|
| `IDLE` | Nenhum pipeline ativo |
| `PROCESSING` | Pipeline em execução |
| `WAITING_FOR_APPROVAL` | Pausado aguardando feedback humano |

Usado pelo `run.sh` como probe de prontidão do backend.

---

## GET /agent/logs

Retorna o ring buffer de logs do servidor (últimas 300 entradas).

**Response:**
```json
{
  "logs": [
    "2026-03-14 10:00:01 - Pipeline started: mouses gamer",
    "2026-03-14 10:00:15 - Node completed: ceo"
  ]
}
```

---

## GET /agent/memory

Consulta o ChromaDB por contexto relevante de decisões passadas. Resultado cacheado em memória com TTL de 30 segundos.

A query fixa usada é `"feedback decision rationale"` com `k=5`.

**Response:**
```json
{ "memory": "Relevant Past Decisions:\n- Topic: notebooks\nDecision: ..." }
```

---

## GET /agent/posts

Lê `data/posts.json` e retorna os artigos gerados.

**Response:**
```json
{ "posts": [ { "title": "...", "slug": "...", "products": [...] } ] }
```

---

## POST /agent/analyze

Executa o `AnalystAgent` sobre o histórico de posts para identificar lacunas de conteúdo.

**Request body:** nenhum

**Response:**
```json
{
  "recommendations": [
    { "topic": "headsets sem fio 2026", "reason": "Sem cobertura para este segmento" }
  ]
}
```

---

## Notas de implementação

### CORS
O servidor permite qualquer origem (`allow_origins=["*"]`). Adequado para desenvolvimento local.

### Reconexão SSE
O endpoint `/agent/runs/{run_id}/stream` aceita conexões a qualquer momento. Se o pipeline já terminou (`done=True`), replica todos os eventos e encerra imediatamente.

### Timeout do proxy frontend
O proxy Next.js aplica timeout de 45 segundos — dimensionado para cobrir a operação mais lenta (Writer: ~38s). O SSE bypassa o proxy e conecta direto ao backend.
