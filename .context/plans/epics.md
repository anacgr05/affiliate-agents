---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-group-epics', 'step-03-elaborate-epics', 'step-04-coverage-mapping']
inputDocuments: ['.context/plans/prd.md', 'docs/architecture.md', 'docs/backend_implementation_plan.md', 'docs/dashboard_plan.md', 'docs/langgraph_architecture.md', 'docs/ui_control_architecture.md']
---

# Affiliate Agents Image Generation - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Affiliate Agents Image Generation, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR01: O Sistema pode gerar textos via agentes LangGraph sem interrupção pela geração de imagem.
FR02: O Sistema pode salvar o plano de publicação assíncrono finalizado em um Banco de Dados relacional.
FR03: O Sistema pode enviar um evento para o Job Queue ao finalizar a geração textual para pedir as imagens associadas ao Post.
FR04: O Leitor da plataforma pode visualizar o artigo com todos os metadados de texto imediatamente.
FR05: O Leitor da plataforma visualiza um estado de espera (Skeleton/Loading) no local da capa caso a imagem ainda não exista (Status: `image_pending`).
FR06: O Sistema no Frontend exibe a imagem definitiva de capa (substituindo o loading) quando ela é renderizada e devolvida à CDN/Banco.
FR07: O Background Worker consegue requisitar prompts estaticamente formados a LLMs (OpenAI) em paralelo a aplicação web.
FR08: O Background Worker executa re-tentativas temporizadas para APIs que retornarem status de limite (Rate Limits).
FR09: O Background Worker converte a resposta em Base64/Bytes enviando para um bucket Cloud (Storage).
FR10: O Background Worker ata a URL definitiva da imagem no registro do post correspondente (PostgreSQL) encerrando o processamento.

### NonFunctional Requirements

NFR01: O tempo de salvamento e disponibilidade de leitura na API do artigo finalizado pelo LangGraph no Banco de Dados deve ser menor que 200ms, sem bloqueio derivado da requisição de imagens.
NFR02: O frontend consumindo a leitura do artigo (reviews/[slug]) deve ter TTFB (Time to First Byte) inferior a 300ms, independentemente se a imagem possui o status ready ou image_pending.
NFR03: O Job Worker de imagens deve suportar indisponibilidade ou rate limit da API da OpenAI garantindo até 3 retries usando backoff exponencial, sem derrubar o processo de renderização dos artigos da fila.
NFR04: Em caso de falha irreversível na geração da imagem (após os retries), o sistema de banco de dados deve registrar status explícito de bloqueio (image_failed) garantindo o acionamento eventual manual.
NFR05: A fila de geração de imagens deve suportar o enfileiramento em massa (Backfill) superior a 10.000 jobs passivos simultaneamente, desacoplados totalmente da saúde do Backend REST da aplicação.
NFR06: Nenhuma requisição simultânea deve ser enviada para a API da OpenAI se o limite de requests-per-minute configurado na chave do cliente já estiver violado (rate-limiting antecipatório no worker).

### Additional Requirements

- Arquitetura baseada em backend assíncrono (`asyncio.create_task`) no FastAPI rodando a pipeline do LangGraph.
- O Frontend Next.js consulta diretamente o FastAPI em portas :8000 via SSE contornando proxies conflitantes (Turbopack node:http workaround).
- Transição de `posts.json` legado para novo fluxo com Banco de Dados Relacional PostgreSQL (via provisionamento no MVP).
- Persistência e memória de decisions no ChromaDB.

## FR Coverage Map

| Requirement | Description | Epic Coverage |
| --- | --- | --- |
| FR01 | Texto gerado via LangGraph sem interrupção | Epic-03 |
| FR02 | Salvar post finalizado em Banco de Dados relacional | Epic-01 |
| FR03 | Clicar evento Job Queue p/ geração de imagem | Epic-03 |
| FR04 | Leitura imediata de textos/metadados no Front | Epic-04 |
| FR05 | Skeleton/Loading via status `image_pending` | Epic-04 |
| FR06 | Substituir Skeleton por imagem real (SSE/Polling) | Epic-04 |
| FR07 | Requisições a IA assíncronas / paralelas na web | Epic-02 |
| FR08 | Re-tentativas (Backoff) para APIs de imagens | Epic-02 |
| FR09 | Conversão Base64 para Object Storage (S3/R2) | Epic-02 |
| FR10 | Salvar Image URL no banco encerrando o processamento | Epic-02 |
| NFR01 | Time-to-Save & TTFB API < 200ms | Epic-01, Epic-03 |
| NFR02 | TTFB Frontend < 300ms | Epic-04 |
| NFR03 | Job worker com 3 retries e backoff na falha de OpenAI | Epic-02 |
| NFR04 | Status 'image_failed' após esgotar retries | Epic-02 |
| NFR05 | Suportar Backfill de 10.000 jobs | Epic-01, Epic-02 |
| NFR06 | Prevenir Rate-limiting antecipatório da OpenAI | Epic-02 |

## Epic List

### Epic-01: Infrastructure & Data Persistence Modernization
**Goal:** Migrate legacy storage and provision essential backend infrastructure to support asynchronous workflows.

*   **Story-01.01: Migrate Database to PostgreSQL**
    *   *Description:* As a Backend Developer, I want to migrate `posts.json` to a PostgreSQL database so that we can support stateful job tracking (`image_pending`, `image_failed`, `ready`).
    *   *Acceptance Criteria:* Database schema maps existing posts attributes. CRUD operations adapted for SQLAlchemy/asyncpg. Migration script included.
    *   *Coverage:* FR02, NFR01
*   **Story-01.02: Setup Job Queue Broker**
    *   *Description:* As a DevOps Engineer, I want to configure the Asynchronous Job Queue broker (e.g. RabbitMQ/Redis for Celery or background tasks configuration) to queue up to 10k passive jobs.
    *   *Acceptance Criteria:* Message broker infrastructure provisioned. Backend can connect and enqueue/dequeue tasks reliably.
    *   *Coverage:* NFR05
*   **Story-01.03: Configure Object Storage Bucket**
    *   *Description:* As a DevOps Engineer, I want to setup and configure permissions for the Cloud Storage bucket (AWS S3/Cloudflare R2) so images can be securely served via CDN.
    *   *Acceptance Criteria:* Bucket created. Backend API has valid access keys with necessary write permissions. Bucket is publicly readable or CDN is attached.
    *   *Coverage:* FR09

### Epic-02: Core Image Worker & OpenAI Integration
**Goal:** Implement the detached background worker responsible for handling OpenAI API calling, retry logic, image upload, and state resolution.

*   **Story-02.01: Implement Image Generation Worker Task**
    *   *Description:* As a Backend Developer, I want to implement a worker task that requests images from OpenAI using static prompts so that image generation runs in parallel with the web application.
    *   *Acceptance Criteria:* Worker ingests payload with prompt. Makes async API call to OpenAI.
    *   *Coverage:* FR07
*   **Story-02.02: Apply Exponential Backoff & Rate-Limiting Protection**
    *   *Description:* As a Backend Developer, I want to implement exponential backoff and rate-limiting prediction in the worker so that OpenAI API limits don't break the queue.
    *   *Acceptance Criteria:* Uses `tenacity` or similar library. Worker tracks local RPM. Retries up to 3 times on 429 warnings. Marks `image_failed` after 3 failed retries.
    *   *Coverage:* FR08, NFR03, NFR06, NFR04
*   **Story-02.03: Object Storage Upload & URL Binding**
    *   *Description:* As a Backend Developer, I want the worker to download the generated image, decode it, upload to Cloud Storage, and update the PostgreSQL record with the permanent URL.
    *   *Acceptance Criteria:* Image uploaded to S3/R2. Database updated with URL. Status changes from `image_pending` to `ready`.
    *   *Coverage:* FR09, FR10

### Epic-03: LangGraph Pipeline & Event Dispatching
**Goal:** Modify the primary text generation path so it is decoupled from the image flow, executing and dispatching in under 200ms API response time.

*   **Story-03.01: Remove Synchronous Image Generation from Text Pipeline**
    *   *Description:* As a Software Engineer, I want to decouple the image generation step from the main LangGraph text pipeline so that textual generation finishes without interruption.
    *   *Acceptance Criteria:* Text generation node outputs complete state. Pipeline writes to Database without waiting for images.
    *   *Coverage:* FR01, NFR01
*   **Story-03.02: Dispatch Event to Image Job Queue**
    *   *Description:* As a Software Engineer, I want the text pipeline to dispatch a job event to the queue immediately after saving text metadata so that image processing begins asynchronously.
    *   *Acceptance Criteria:* Node after DB-save triggers queue dispatch. Event contains Post ID and parameters for prompt. API responds immediately after.
    *   *Coverage:* FR03

### Epic-04: Frontend Async Resilience & UI State
**Goal:** Adapt the Next.js Frontend to seamlessly handle posts whose images are still being generated by the asynchronous worker backend.

*   **Story-04.01: Next.js Fast Page Load (Metadados Otimizados)**
    *   *Description:* As a Frontend Developer, I want the `reviews/[slug]` page to load immediately with text metadata, ensuring a TTFB under 300ms regardless of image status.
    *   *Acceptance Criteria:* Page logic decoupled from missing image data. Text properly rendered upfront.
    *   *Coverage:* FR04, NFR02
*   **Story-04.02: UI Skeleton for `image_pending`**
    *   *Description:* As a User, I want to see a Skeleton/Loading state where the post cover should be if the status is `image_pending` so I know an image is generating.
    *   *Acceptance Criteria:* Next.js component conditionally renders animated Skeleton placeholder if picture prop is null / status is `image_pending`.
    *   *Coverage:* FR05
*   **Story-04.03: Live Image Replacement (SSE)**
    *   *Description:* As a User, I want the page to automatically replace the Skeleton with the finalized image once it is rendered and available on the CDN/DB.
    *   *Acceptance Criteria:* Frontend establishes connection (via direct SSE or short-polling on :8000) listening for state change on current post ID. Updates image src when `ready` triggers.
    *   *Coverage:* FR06
