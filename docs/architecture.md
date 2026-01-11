# Affiliate Agent Stack - Project Plan

## Vision
Create a stack of specialized AI agents to build and manage a high-performance affiliate marketing website. The goal is to generate real value for the user through price comparisons, reviews, and detailed product analysis, while maximizing SEO and conversion rates.

## Architecture

### Agent Roles
1.  **CEO Agent**: Orchestrates the overall strategy, sets goals, and oversees the other agents.
2.  **Product Manager (PM)**: Defines features, prioritizes tasks, and ensures the product meets user needs.
3.  **Portfolio Manager**: Selects products to promote based on market trends and profitability.
4.  **Data Analyst (Performance)**: Analyzes traffic, conversion rates, and SEO metrics to optimize the site.
5.  **Developers**:
    *   *Frontend Dev*: Builds the Next.js/React interface.
    *   *Backend Dev*: Handles API integrations and server-side logic.
6.  **Content/SEO Specialist**: Ensures all content is optimized for Google Organic search.

### Tech Stack
*   **LLM Provider**: OpenRouter (access to various models).
*   **Search/Data**: SearchAPI (for marketplaces and product data).
*   **Frontend**: Next.js (Recommended for SEO).
*   **Backend/Orchestration**: Python (LangChain/LangGraph or similar) for agents.
*   **Database**: (To be defined - likely PostgreSQL or Supabase).

## Directory Structure
*   `/agents`: Source code for the AI agents.
*   `/frontend`: The affiliate website (Next.js).
*   `/docs`: Documentation and planning.

## External Services Required
*   **OpenRouter API Key**: For LLM inference.
*   **SearchAPI Key**: For fetching product data across marketplaces.
*   **Hosting**: Vercel (for Frontend) + Railway/Render (for Python Agents) recommended.
