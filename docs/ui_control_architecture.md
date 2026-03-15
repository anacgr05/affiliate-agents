# Frontend e Proxy

## Estrutura de arquivos relevantes

```
frontend/
├── app/
│   ├── admin/dashboard/page.tsx       # Dashboard principal
│   └── api/agent/[...path]/route.ts   # Proxy catch-all
└── next.config.ts
```

---

## Proxy catch-all (`app/api/agent/[...path]/route.ts`)

Todas as chamadas HTTP do dashboard para o backend passam por este handler, exceto o stream SSE.

### Por que usar `node:http` com `agent: false`

O `fetch` nativo do Node.js usa `undici` com pool de conexões. O Uvicorn é configurado com `--timeout-keep-alive 0`, fechando conexões ociosas no lado do servidor. O `undici` não percebe que a conexão foi fechada e tenta reutilizá-la, causando `ECONNRESET` em requisições alternadas.

A solução é `node:http` com `agent: false`, que abre um socket TCP novo a cada requisição, eliminando completamente o pool.

```typescript
const req = httpRequest({
    hostname: "localhost",
    port: 8000,
    path: `/agent/${path.join("/")}`,
    method,
    agent: false, // sem pool de conexões
    // ...
});
req.setTimeout(45_000, () => req.destroy(new Error("backend timeout")));
```

### Timeout de 45 segundos

Dimensionado para cobrir a operação legítima mais lenta (Writer LLM: ~38s). Para backends inacessíveis, `ECONNREFUSED` dispara em menos de 1 segundo.

### Rota catchall

O arquivo `[...path]/route.ts` captura qualquer subpath de `/api/agent/`. Exemplos:

| Requisição do browser | Path no handler | Chamada ao backend |
|-----------------------|-----------------|--------------------|
| `POST /api/agent/start` | `["start"]` | `POST /agent/start` |
| `GET /api/agent/logs` | `["logs"]` | `GET /agent/logs` |
| `POST /api/agent/feedback` | `["feedback"]` | `POST /agent/feedback` |

O handler suporta GET e POST. A rota SSE (`/agent/runs/{id}/stream`) tecnicamente passa pelo mesmo handler, mas o dashboard nunca a usa dessa forma — conecta direto ao backend.

---

## SSE: conexão direta ao backend

O `EventSource` no dashboard **bypassa o proxy** e conecta diretamente ao backend:

```typescript
const backendBase = `http://${window.location.hostname}:8000`;
const es = new EventSource(`${backendBase}/agent/runs/${runId}/stream`);
```

### Por que contornar o Next.js para SSE

O Turbopack (servidor de desenvolvimento do Next.js) armazena respostas em buffer e só as entrega ao cliente depois que o stream é fechado. Isso tornaria o SSE inútil — todos os eventos apareceriam de uma vez no fim do pipeline. A conexão direta ao backend na porta 8000 entrega os eventos em tempo real.

### `next.config.ts`

```typescript
const nextConfig: NextConfig = {
    allowedDevOrigins: ["192.168.1.11", "192.168.3.72"],
};
```

`allowedDevOrigins` permite que o dashboard seja acessado de outros dispositivos na rede local durante o desenvolvimento. Nenhum rewrite de URL é necessário pois o proxy é implementado diretamente no route handler.

---

## Ciclo de vida de uma execução no frontend

1. Usuário digita um tópico e clica em "Iniciar"
2. Dashboard faz `POST /api/agent/start` (via proxy) — recebe `run_id`
3. Dashboard cria `EventSource` direto para `http://localhost:8000/agent/runs/{run_id}/stream`
4. Eventos `node_completed` chegam em tempo real — dashboard atualiza a barra de progresso e o log de mensagens
5. Evento `waiting_approval` exibe o painel de aprovação com o `content_plan`
6. Usuário aprova ou rejeita — dashboard faz `POST /api/agent/feedback` (via proxy)
7. Evento `pipeline_completed` encerra o `EventSource` e atualiza a lista de posts

---

## Polling complementar

O dashboard complementa o SSE com dois intervalos de polling HTTP (via proxy):

| Dado | Intervalo | Endpoint |
|------|-----------|----------|
| Logs do servidor | 5s (processing) / 30s (idle) | `GET /agent/logs` |
| Memória + posts | 30s (apenas quando idle) | `GET /agent/memory`, `GET /agent/posts` |

O polling de memória e posts também é disparado manualmente ao receber `pipeline_completed`.
