---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish']
inputDocuments: ['README.md', 'docs/architecture.md', 'docs/backend_implementation_plan.md', 'docs/dashboard_plan.md', 'docs/langgraph_architecture.md', 'docs/memory_and_models.md', 'docs/ui_control_architecture.md']
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 7
workflowType: 'prd'
classification:
  projectType: "Web App & API Backend"
  domain: "Content Automation / AI Agents"
  complexity: "Medium"
  projectContext: "brownfield"
---

# Product Requirements Document - Image Generation Feature

**Author:** Insider
**Date:** 2026-05-17

## Executive Summary

A feature de **Geração de Imagens Assíncrona** substitui os placeholders genéricos dos artigos por imagens contextuais geradas via integração com o modelo de imagem do ChatGPT. Ao desacoplar o processo síncrono do Pipeline de Orquestração LLM (LangGraph), o sistema ataca a baixa conversão visual observada e resolve problemas onde a UX era degradada, entregando um frontend de alta confiabilidade. Este componente orquestrativo opera inteiramente em background, garantindo escalabilidade tanto para a geração contínua de novos conteúdos quanto para o reprocessamento de todo o acervo histórico (backfill).

### What Makes This Special

O diferencial técnico central desta entrega é a orquestração invisível aliada à persistência moderna. O projeto transcende o trabalho manual fragmentado, implementando uma fila gerenciada (Job Queue) unida a uma camada transacional por banco relacional. Isso produz uma experiência final que:
- Prende a atenção do usuário por correlação temática visual direta com o post.
- Mitiga o amadorismo associado a placeholders genéricos na versão hospedada.
- Eleva o branding para um perfil robusto e profissional sem degradar ou dar "timeout" no fluxo de criação original do texto afiliado.

## Project Classification

- **Project Type:** Web App & API Backend
- **Domain:** Content Automation / AI Agents
- **Complexity:** Medium (processamento com workflow job queue assíncrono acoplado ao backfill histórico e streaming da API original).
- **Project Context:** Brownfield (integração refatorativa em repositório já contendo FastAPI, Next.js, e LangGraph preexistente com flat file database).

## Success Criteria

### User Success

- Aumento no Tempo de Permanência (Bounce Rate) reduzido devido ao melhor apelo visual.
- Zero atrito visual ao consumir os artigos (placeholders nativos removidos).

### Business Success

- Aumento na taxa de clique (CTR) nos links de afiliados (+15% projetado).
- Geração automatizada ponta-a-ponta, resultando na eliminação de horas gastas com curadoria de imagens manuais.

### Technical Success

- Confiabilidade: Job de imagem com sucesso em >95% das tentativas com fallback adequado.
- Performance: Enfileiramento não bloqueia o pipeline original de geração em LangGraph (< 200ms na publicação).

### Measurable Outcomes

- Métrica 1: Taxa de finalização de geração de imagem sem error rate excedido.
- Métrica 2: Aumento do CTR nos referals e diminuição do Bounce Rate orgânico nos artigos criados.

## Product Scope

### MVP - Minimum Viable Product

- Migração de `posts.json` para banco de dados relacional (ex: PostgreSQL).
- Interceptação da geração síncrona de imagem para um modelo assíncrono (Job Queue / Background tasks).
- Endpoint para busca/leitura no Frontend atualizada para leitura do novo esquema via API.

### Growth Features (Post-MVP)

- Backfill automático (regenerar capas perdidas do acervo legado via enfileiramento inteligente).
- Painel de controle no admin dashboard mostrando estado de fila, retry rates e falhas (Pending/Failed Jobs).

### Vision (Future)

- Teste A/B Dinâmico de Capas: testando simultaneamente até duas imagens geradas para mensurar a de maior clique e conversão.

## User Journeys

### Jornada 1: O "Aha Moment" da Criação Dinâmica (Admin)
O gestor entra no Dashboard e inicia uma pauta. Os agentes do LangGraph trabalham e pausam no *Human Node*. Ele lê o plano e aprova. Imediatamente o texto é escrito no banco e dispara um evento. Ele visualiza a página do Post na interface que naquele primeiro segundo mostra um *Placeholder/Skeleton de imagem carregando*. Enquanto ele lê a introdução e observa os cards com estrelas e preços que o PM Agent trouxe, o *Job Queue* é finalizado no background. Em segundos (ou um F5), a imagem cover temática hiper-relevante aparece. O "Aha moment" é quando ele não precisa abrir o MidJourney nem buscar foto no banco de imagens - a publicação final fica pronta, rica e contextual.

### Jornada 2: A Operação de Resgate Histórico (DevOps/Admin)
A base de dados é populada com milhares de registros de `posts.json` antigos, recém persistidos no PostgreSQL porém sem imagens. O Desenvolvedor acessa a nova rota da API via um gatilho de *Backfill*. O `ImageBackfillWorker` inicia e o desenvolvedor acompanha em um console/logs a conversão do "Prompt Baseado no Conteúdo Antigo" disparando requisições em lote para o ChatGPT. Ele vê a contabilidade (Pending: 40, Ready: 15, Failed: 2). Se o modelo do ChatGPT dá erro (rate limit), o desenvolvedor sorri de alívio porque a camada de banco apenas fará o "retry", preservando todo o artigo sem destruir o pipeline local.

### Journey Requirements Summary

- Necessidade de estado de ponte no Frontend (Loading/Skeleton) quando imagem em "image_pending".
- Fila assíncrona gerenciada não bloqueante acionada após Human Node.
- Job Worker com retentativas independentes, com fallback estruturado.
- Funcionalidade de processamento em lote em lote (Backfill).
- Banco de dados suportando persistência segura de estado de imagem (ID do Asset, Status, Falhas)

## Domain-Specific Requirements

### Technical Constraints & AI Domain Patterns
- **Rate Limiting & Retry**: Integração com APIs externas (ex: OpenAI) com limites rígidos (Rate Limits). O sistema background *deve* prever backoff exponencial.
- **Cost Management**: Jobs de imagem representam custo alto por call. Evitar loops infinitos de retry em prompts problemáticos (`max_retries`).
- **Resilience**: Falhas no LLM não podem reverter nem invalidar o texto ou o plano já aprovados. A arquitetura de fila garante a dissociação do pipeline principal.

## Technical Architecture & Implementation Deep Dive

### Backend/Worker Architecture
- **Worker & Job Queue**: O processamento em plano de fundo utilizará uma solução baseada em mensageria (ex: Celery + Redis ou um simples Redis Queue / RQ) para coordenar as ordens de "gerar imagem" desacopladas da requisição principal da interface REST.
- **Storage de Assets**: A aplicação fará o download físico da imagem retornada pela OpenAI e persistirá em um serviço de Object Storage (como AWS S3 ou Cloudflare R2), guardando apenas a URL defintiva/CDN no banco de dados. Isso previne falhas de URLs temporárias dos provedores.
- **Rate Limiting Handling**: Utilização nativa da biblioteca `tenacity` (Exponential Backoff) diretamente na camada do Worker para enfileirar e segurar as requisições quando os limites (429 Too Many Requests) forem atingidos pelo serviço da OpenAI.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Execution & Efficiency MVP - Foco primário na transição técnica de JSON base para PostgreSQL e integração de fila assíncrona não bloqueante de Imagens. O ganho de valor não requer UI elaborada neste instante, apenas garantia e resiliência na entrega automatizada da imagem.
**Resource Requirements:** Configuração para desenvolvedores full-stack (Backend + Front Next.js App Router). Foco total em pipeline de dados robusto.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Jornada 1: Geração dinâmica de artigos, aprovação do gestor e injeção do componente Skeleton no front end, seguido do aparecimento final da renderização da imagem pós-assincronismo.

**Must-Have Capabilities:**
- Banco de dados em PostgreSQL;
- Separação da geração das imagens no fluxo LangGraph utilizando Background Jobs;
- Integração Frontend exibindo estados de loading/pendente (`image_pending`);
- Envio e persistência real em Cloud Storage para URLs definitivas;
- Tratamento de Rate Limiting simples do LLM (retry/tenacity).
- *Decisão de Escopo*: Prompts de imagem serão Hardcoded no worker para o MVP visando velocidade de entrega.

### Post-MVP Features

**Phase 2 (Growth - Pós-MVP):**
- **Backfill em Lote:** O script e interface para converter artigos antigos (`posts.json`) passará para fase dois. A prioridade central do MVP deve ser artigos "daqui para frente".
- Painel para Visualização/Re-tentativa de Jobs que falharem no Dashboard Admin.
- Edição de configurações do prompt de imagem via UI do Admin Dashboard.

**Phase 3 (Expansion):**
- Testes A/B Dinâmicos para a escolha de melhor geração de imagem (clique-conversão).

### Risk Mitigation Strategy

**Technical Risks:** Gargalos com API OpenAI. *Mitigação:* Usar backoff exponencial e persistência de falha no PG.
**Market Risks:** Baixo impacto nos referals. *Mitigação:* Medir Bounce Rate estritamente com analytics.
**Resource Risks:** Extrapolar o escopo inicial com DevOps de mensageria. *Mitigação:* Utilizar soluções simples para o Queue caso Celery exija muita infra (ex: Redis Queue leve ou FastAPI BackgroundTasks para MVP).

## Functional Requirements

### Módulo: Processamento Principal
- FR01: O Sistema pode gerar textos via agentes LangGraph sem interrupção pela geração de imagem.
- FR02: O Sistema pode salvar o plano de publicação assíncrono finalizado em um Banco de Dados relacional.
- FR03: O Sistema pode enviar um evento para o Job Queue ao finalizar a geração textual para pedir as imagens associadas ao Post.

### Módulo: Interface de Usuário (Admin / Leitor)
- FR04: O Leitor da plataforma pode visualizar o artigo com todos os metadados de texto imediatamente.
- FR05: O Leitor da plataforma visualiza um estado de espera (Skeleton/Loading) no local da capa caso a imagem ainda não exista (Status: `image_pending`).
- FR06: O Sistema no Frontend exibe a imagem definitiva de capa (substituindo o loading) quando ela é renderizada e devolvida à CDN/Banco.

### Módulo: Background Worker & Resiliência
- FR07: O Background Worker consegue requisitar prompts estaticamente formados a LLMs (OpenAI) em paralelo a aplicação web.
- FR08: O Background Worker executa re-tentativas temporizadas para APIs que retornarem status de limite (Rate Limits).
- FR09: O Background Worker converte a resposta em Base64/Bytes enviando para um bucket Cloud (Storage).
- FR10: O Background Worker ata a URL definitiva da imagem no registro do post correspondente (PostgreSQL) encerrando o processamento.

## Non-Functional Requirements

### Performance & Latência (UX)
- NFR01: O tempo de salvamento e disponibilidade de leitura na API do artigo finalizado pelo LangGraph no Banco de Dados deve ser menor que `200ms`, sem bloqueio derivado da requisição de imagens.
- NFR02: O frontend consumindo a leitura do artigo (`reviews/[slug]`) deve ter TTFB (Time to First Byte) inferior a `300ms`, independentemente se a imagem possui o status ready ou `image_pending`.

### Confiabilidade & Resiliência (Reliability)
- NFR03: O Job Worker de imagens deve suportar indisponibilidade ou rate limit da API da OpenAI garantindo até `3 retries` usando backoff exponencial, sem derrubar o processo de renderização dos artigos da fila.
- NFR04: Em caso de falha irreversível na geração da imagem (após os retries), o sistema de banco de dados deve registrar status explícito de bloqueio (`image_failed`) garantindo o acionamento eventual manual.

### Escalabilidade (Scalability)
- NFR05: A fila de geração de imagens deve suportar o enfileiramento em massa (Backfill) superior a `10.000` jobs passivos simultaneamente, desacoplados totalmente da saúde do Backend REST da aplicação.

### Integração & Custos
- NFR06: Nenhuma requisição simultânea deve ser enviada para a API da OpenAI se o limite de `requests-per-minute` configurado na chave do cliente já estiver violado (rate-limiting antecipatório no worker).
