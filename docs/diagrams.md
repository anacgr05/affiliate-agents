# Diagramas de Arquitetura

> Gerado em: 2026-03-14
> Versão atual do pipeline: SSE + `graph.astream()` + `asyncio.Event` para human-in-the-loop
> Critic: `with_structured_output(CriticResult)` + sub-scores por dimensão (SEO · CRO · Diferenciação · CEO)

---

## Diagrama Simplificado

Visão macro do fluxo de dados entre as camadas.

```mermaid
flowchart LR
    User(["👤 Usuário"])

    subgraph FE["Frontend — Next.js :3000"]
        Dashboard["Admin Dashboard"]
        Posts["Página de Posts"]
        Proxy["API Proxy\n/api/agent/[...path]"]
    end

    subgraph BE["Backend — FastAPI :8000"]
        API["Endpoints REST\n/agent/start\n/agent/feedback\n/agent/status"]
        SSE["SSE Stream\n/agent/runs/{id}/stream"]
        Pipeline["Pipeline LangGraph"]
    end

    subgraph LG["Grafo de Agentes"]
        CEO["CEO\nEstratégia editorial"]
        PM_SEARCH["Portfolio Manager\nPesquisa de produtos"]
        PM_PLAN["Product Manager\nPlano de conteúdo"]
        Critic{"Crítico\nScore > 8?"}
        Human["Human Review\n(interrupt)"]
        Writer["Writer\nGera artigo"]
    end

    Data[("data/posts.json")]

    User -->|"POST start"| Dashboard
    Dashboard -->|"proxy"| Proxy
    Proxy -->|"node:http agent:false"| API
    API -->|"asyncio.create_task"| Pipeline
    Pipeline --> CEO --> PM_SEARCH --> PM_PLAN --> Critic
    Critic -->|"❌ ≤ 8 (max 3x)"| PM_PLAN
    Critic -->|"✅ > 8"| Human
    Human -->|"aprovado"| Writer
    Human -->|"rejeitado"| PM_PLAN
    Writer --> Data
    Data -->|"leitura SSG"| Posts

    BE -->|"eventos SSE"| Proxy
    Proxy -->|"EventSource direto :8000"| Dashboard
```

---

## Diagrama Completo

Detalhe de cada componente, estado do grafo, endpoints e tipos de evento SSE.

```mermaid
flowchart TD
    %% ── Entrada ──────────────────────────────────────────────────────────────
    User(["👤 Usuário\nbrowser"])

    subgraph FE["Frontend — Next.js :3000"]
        direction TB
        Dashboard["Admin Dashboard\napp/admin/dashboard/page.tsx"]
        PostsPage["Página de Posts\napp/posts/[slug]/page.tsx"]

        subgraph Proxy["API Proxy — app/api/agent/[...path]/route.ts"]
            HTTP["node:http\nagent:false\ntimeout: 45s"]
        end
    end

    subgraph BE["Backend — FastAPI :8000"]
        direction TB

        subgraph Endpoints["Endpoints"]
            Start["POST /agent/start\n→ cria run_id, dispara pipeline"]
            Feedback["POST /agent/feedback\n→ injeta feedback, seta asyncio.Event"]
            Stream["GET /agent/runs/{id}/stream\n→ SSE com replay buffer"]
            Status["GET /agent/status"]
            Logs["GET /agent/logs"]
            Memory["GET /agent/memory"]
            PostsEP["GET /agent/posts"]
        end

        subgraph RunStore["Run Store (_runs dict)"]
            Events["events[]\n(replay buffer)"]
            Queues["queues set()\n(subscribers ativos)"]
            FeedbackEv["feedback: asyncio.Event\n(pausa human-in-the-loop)"]
            Done["done: bool"]
            Config["config: thread_id"]
        end

        subgraph SSEEvents["Tipos de Evento SSE"]
            Ev1["pipeline_started"]
            Ev2["node_completed\n{node, messages, plan}"]
            Ev3["waiting_approval"]
            Ev4["pipeline_completed"]
            Ev5["error"]
        end
    end

    subgraph LG["Grafo LangGraph — graph/workflow.py + graph/nodes.py"]
        direction TB

        subgraph State["AgentState (TypedDict)"]
            S1["messages: List[BaseMessage]"]
            S2["current_topic: str"]
            S3["recommendations: List[dict]"]
            S4["content_plan: dict"]
            S5["critic_feedback: str"]
            S6["human_feedback: str"]
            S7["ceo_strategy: str"]
            S8["critic_attempts: int"]
        end

        CEO["🏢 ceo_node\nCEOAgent.define_strategy()\nLê posts existentes\n→ ceo_strategy"]
        Portfolio["💼 portfolio_node\nPortfolioManagerAgent\n.analyze_and_recommend()\n.search_products() → SearchAPI\n→ recommendations"]
        ProdMgr["📝 product_manager_node\nProductManagerAgent.create_plan()\n← topic + recommendations\n← critic_feedback + ceo_strategy\n→ content_plan"]
        Critic["🧐 critic_node\nCriticAgent.review_plan()\n← content_plan + ceo_strategy\n← memory_context (ChromaDB)\n→ CriticResult tipado\n(SEO · CRO · Diff · CEO scores)"]

        ScoreCheck{"overall_score > 8.0\nE ceo_alignment >= 7.0\nE attempts < 3?"}

        Human["👤 human_node\n← human_feedback (injetado\n  via POST /agent/feedback)\n→ mensagem de aprovação"]

        HumanCheck{"human_feedback\nstartswith('y')?"}

        Writer["✍️ writer_node\nProductManagerAgent.create_content()\nPrice enrichment (SearchAPI)\nPlaceholder hero image\n→ salva data/posts.json\n→ salva MemoryManager"]

        CEO --> Portfolio --> ProdMgr --> Critic
        Critic --> ScoreCheck
        ScoreCheck -->|"❌ reprovado\nfeedback rico: score+issues+recs"| ProdMgr
        ScoreCheck -->|"✅ aprovado\n(interrupt_before)"| Human
        Human --> HumanCheck
        HumanCheck -->|"'y' — aprovado"| Writer
        HumanCheck -->|"'n...' — rejeitado"| ProdMgr
        Writer --> END(["END"])
    end

    subgraph Ext["Serviços Externos"]
        OpenRouter["OpenRouter API\nLLM calls"]
        SearchAPI["SearchAPI\nGoogle Shopping"]
        ChromaDB[("ChromaDB\nmemory_db/\n+ HuggingFace\nall-MiniLM-L6-v2")]
    end

    subgraph Data["Dados Gerados (gitignored)"]
        PostsFile[("data/posts.json\narraydeposts gerados")]
    end

    %% ── Conexões principais ──────────────────────────────────────────────────
    User -->|"clica 'Iniciar'"| Dashboard
    Dashboard -->|"POST /api/agent/start"| Proxy
    Proxy -->|"node:http agent:false"| Start
    Start -->|"asyncio.create_task"| CEO

    BE -->|"node_completed events"| Stream
    Stream -->|"EventSource direto\nhttp://hostname:8000\n(bypassa Turbopack)"| Dashboard

    Dashboard -->|"POST /api/agent/feedback"| Proxy
    Proxy --> Feedback
    Feedback -->|"update_state + Event.set()"| Human

    Writer --> PostsFile
    PostsFile -->|"leitura em build/SSG"| PostsPage

    CEO & Portfolio & ProdMgr & Critic & Writer -->|"LLM calls"| OpenRouter
    Portfolio & Writer -->|"product search"| SearchAPI
    Critic -->|"retrieve_relevant_context"| ChromaDB
    Writer -->|"add_decision"| ChromaDB
```

---

## Como manter atualizado

Toda vez que o fluxo do grafo mudar (novos nós, novas arestas, nova lógica de roteamento), edite este arquivo:

1. **Nó novo** → adicione em ambos os diagramas
2. **Threshold do crítico mudou** → atualize `score > 8.0` e o label da aresta `ScoreCheck`
3. **Novo tipo de evento SSE** → adicione em `SSEEvents` no diagrama completo
4. **Nova integração externa** → adicione em `Ext`

O diagrama simplificado serve para onboarding rápido; o completo é a referência técnica.
