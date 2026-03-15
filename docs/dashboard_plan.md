# Dashboard — Funcionalidades

Arquivo: `frontend/app/admin/dashboard/page.tsx`

Rota: `/admin/dashboard`

---

## Layout

O dashboard usa um grid de 3 colunas em telas grandes (`lg:grid-cols-3`). A coluna principal (2/3 da largura) exibe o progresso do pipeline, a conversa dos agentes e o terminal. A coluna lateral (1/3) contém os controles e painéis de informação.

```
┌────────────────────────────┬──────────────────┐
│  Barra de progresso        │  Nova Missão      │
│  (pipeline steps)          │                  │
├────────────────────────────│  Insights        │
│  Conversa dos Agentes      │  (Analista)      │
│  (mensagens em markdown)   │                  │
│                            │  [Aprovação]     │
│                            │  (quando ativo)  │
├────────────────────────────│                  │
│  Terminal do Backend       │  Memória         │
│  (ring buffer de logs)     │                  │
└────────────────────────────│  Rascunhos       │
                             └──────────────────┘
```

---

## Componentes e funcionalidades

### Status indicator

Exibe o estado atual do sistema no cabeçalho:

| Status | Label | Visual |
|--------|-------|--------|
| `IDLE` | Aguardando | Bolinha cinza |
| `PROCESSING` | Processando... | Bolinha verde animada (pulse) |
| `WAITING_FOR_APPROVAL` | Aguardando Aprovação | Bolinha amarela animada |

### Barra de progresso do pipeline

Exibida durante a execução e por 8 segundos após a conclusão. Mostra os 6 passos do pipeline:

```
CEO → Portfólio → Produto → Crítico → Aprovação → Redator
```

Cada passo tem três estados visuais:
- Pendente: círculo cinza
- Atual: círculo azul com pulse e anel
- Concluído: ícone de checkmark verde

Uma linha de status abaixo dos ícones descreve o que o agente atual está fazendo. Um contador de tempo decorrido é exibido no canto direito.

### Conversa dos Agentes

Painel de scroll que exibe todas as mensagens `node_completed` recebidas via SSE. Cada mensagem é renderizada com:

- Cabeçalho colorido com nome e emoji do agente
- Conteúdo em markdown via `ReactMarkdown`
- Cores e bordas distintas por agente:

| Agente | Cor |
|--------|-----|
| CEO | Índigo |
| Gestor de Portfólio | Azul |
| Gestor de Produto | Esmeralda |
| Crítico | Âmbar |
| Redator | Roxo |
| Você (humano) | Azul-céu |

### Terminal do Backend

Painel de altura fixa (144px) com fundo escuro, exibindo o ring buffer de logs do servidor. Atualizado a cada 5 segundos durante o processamento e a cada 30 segundos quando ocioso.

### Nova Missão

Campo de texto + botão "Iniciar". Ao pressionar Enter ou clicar em Iniciar:

1. Faz `POST /api/agent/start` com retry automático (3 tentativas, 1s entre elas)
2. Armazena o `run_id` retornado
3. Conecta o `EventSource` ao stream SSE

O campo é limpo imediatamente após o envio para evitar submissão dupla.

### Insights (Analista)

Chama `POST /api/agent/analyze` e exibe recomendações de tópicos ainda não cobertos. Cada recomendação é clicável e preenche o campo "Nova Missão" com o tópico sugerido.

### Painel de Aprovação

Exibido apenas quando `status === "WAITING_FOR_APPROVAL"` e o `content_plan` está disponível. Mostra:

- Tópico, ângulo, público-alvo e produtos selecionados
- Textarea para comentários (obrigatório apenas ao rejeitar)
- Botões "Rejeitar" e "Aprovar"

Ao aprovar ou rejeitar, chama `POST /api/agent/feedback` e volta ao estado `PROCESSING` enquanto o pipeline retoma.

### Banco de Memória

Exibe o resultado da query RAG (`GET /agent/memory`) — decisões passadas relevantes recuperadas do ChromaDB. Atualizado a cada 30 segundos quando ocioso e imediatamente após um pipeline completar.

### Rascunhos

Lista os 3 artigos mais recentes de `data/posts.json` (via `GET /agent/posts`), exibindo título e slug. Atualizado junto com o painel de memória.

---

## Estado React

| Estado | Tipo | Descrição |
|--------|------|-----------|
| `status` | string | IDLE / PROCESSING / WAITING_FOR_APPROVAL |
| `runId` | string \| null | ID do run SSE atual |
| `pipeline` | PipelineData \| null | Estado da barra de progresso (ativo) |
| `pipelineFinished` | PipelineData \| null | Estado final (exibido por 8s após conclusão) |
| `logs` | array | Mensagens dos agentes acumuladas |
| `plan` | object \| null | `content_plan` do ProductManager |
| `memory` | string | Texto do ChromaDB |
| `posts` | array | Artigos de `data/posts.json` |
| `serverLogs` | string[] | Ring buffer de logs |
| `recommendations` | array | Sugestões do AnalystAgent |
| `elapsed` | number | Segundos decorridos desde o início |
