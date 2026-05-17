# Post-Mortem Comercial com Claude — Estrutura de Pensamento

---

## Visão Geral do Sistema

O objetivo é ter um agente (ou fluxo de agentes) capaz de:

1. **Receber o contexto da ação comercial** (campanha, promoção, lançamento, etc.)
2. **Selecionar e analisar métricas relevantes** de um catálogo pré-definido
3. **Redigir o post-mortem** seguindo um template padronizado
4. **Entregar o documento final** em formato utilizável

---

## Componentes do Sistema

### 1. Catálogo de Métricas (Knowledge Base)

Um documento de referência — pode ser um `.md`, `.json` ou até uma skill — que descreve:

- **Quais métricas existem** (ex: taxa de conversão, CAC, ROAS, ticket médio, churn pós-campanha...)
- **De onde vêm** (qual tabela, query base, sistema de origem)
- **O que significam** (definição de negócio, fórmula de cálculo)
- **Quando são relevantes** (ex: "ROAS só faz sentido para campanhas pagas")

> **Ideia de implementação:** isso pode ser uma skill que o agente consulta para entender o "mapa" de métricas disponíveis antes de decidir quais puxar.

---

### 2. Input do Usuário (Disparo do Post-Mortem)

O usuário fornece no comando:

```
Faça o post-mortem da [ação X].
Métricas a analisar: conversão, CAC, ticket médio, NPS pós-ação.
Período: 01/03 a 15/03/2026.
```

Ou de forma mais aberta:

```
Faça o post-mortem da campanha de Black Friday.
Use as métricas de performance de mídia paga + retenção.
```

O agente deve ser capaz de:

- Interpretar quais métricas foram pedidas
- Cruzar com o catálogo para saber onde buscar os dados
- Identificar se falta alguma métrica crítica e perguntar ao usuário

---

### 3. Camada de Análise de Dados

Duas abordagens possíveis:

**A) Agente executa queries diretamente**
- Conectado a BigQuery / banco de dados via tool ou MCP
- Recebe as queries base do catálogo de métricas e executa
- Vantagem: mais autônomo
- Risco: precisa de controle de acesso e validação das queries

**B) Usuário traz os dados, agente interpreta**
- Usuário cola tabelas, CSVs ou resultados já extraídos
- Agente interpreta e extrai os insights
- Mais simples de implementar, menos automatizado

> **Recomendação inicial:** começar com B para validar o template e a qualidade do documento, migrar para A depois.

---

### 4. Template Padrão do Post-Mortem

Estrutura sugerida para o documento gerado:

```
# Post-Mortem: [Nome da Ação]
**Data da ação:** ...
**Período analisado:** ...
**Responsável:** ...

---

## 1. Resumo Executivo
[2-3 parágrafos com o que foi a ação, resultado geral e principal aprendizado]

## 2. Contexto e Objetivo
- O que era a ação?
- Qual era o objetivo principal (meta)?
- Hipótese inicial

## 3. O que foi planejado vs. o que aconteceu
| Métrica         | Meta     | Realizado | Variação |
|-----------------|----------|-----------|----------|
| Conversão       | X%       | Y%        | +/-Z pp  |
| CAC             | R$ X     | R$ Y      | ...      |
| ...             |          |           |          |

## 4. Análise por Métrica
[Para cada métrica selecionada: o que aconteceu, por quê, o que influenciou]

## 5. O que funcionou
- Bullet points objetivos

## 6. O que não funcionou
- Bullet points objetivos

## 7. Causas Raiz
[Análise mais profunda dos desvios negativos]

## 8. Aprendizados e Recomendações
- [Aprendizado] → [Ação recomendada para próxima vez]

## 9. Próximos Passos
- Responsável | Ação | Prazo
```

---

## Fluxo de Execução

```
[Usuário dispara o comando]
        ↓
[Agente lê o catálogo de métricas]
        ↓
[Agente identifica quais métricas são relevantes para a ação]
        ↓
[Agente busca / recebe os dados]
        ↓
[Agente interpreta os dados e extrai insights]
        ↓
[Agente preenche o template do post-mortem]
        ↓
[Documento final entregue]
```

---

## Pontos em Aberto / Decisões a Tomar

| Questão | Opção A | Opção B |
|---|---|---|
| Fonte dos dados | Agente executa queries | Usuário fornece os dados |
| Catálogo de métricas | Skill dedicada | Documento estático anexado ao contexto |
| Output | `.docx` gerado | Markdown no chat |
| Seleção de métricas | Usuário especifica no comando | Agente sugere e usuário confirma |
| Validação do documento | Critic agent revisa antes de entregar | Entrega direta |

---

## Sugestão de Próximos Passos

1. **Montar o catálogo de métricas** — o documento com todas as métricas possíveis, suas definições e origens
2. **Definir o template final** — ajustar as seções acima com o que faz sentido para o contexto da empresa
3. **Prototipar com dados reais** — rodar um post-mortem de uma ação passada manualmente para validar o fluxo
4. **Depois: automatizar a camada de dados** — conectar ao BigQuery ou fonte de dados real
