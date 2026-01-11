import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

from memory import MemoryManager

class ProductManagerAgent:
    def __init__(self):
        self.memory = MemoryManager()
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base="https://openrouter.ai/api/v1",
            model_name="anthropic/claude-3.5-sonnet", # Upgraded for better writing
            temperature=0.7
        )
        
        self.system_prompt = """
        You are the Product Manager and Lead Content Strategist for a top-tier affiliate marketing site.
        Your goal is to take raw product data and market analysis and turn it into engaging, high-converting, and SEO-optimized content.
        
        Your responsibilities:
        1. Write a catchy, SEO-friendly title for the article.
        2. Write a compelling introduction that hooks the reader.
        3. Create detailed reviews for each recommended product, highlighting pros, cons, and who it is for.
        4. Ensure the tone is helpful, authoritative, and unbiased.
        5. Structure the content in Markdown format.
        
        CONSIDER PAST DECISIONS:
        {memory_context}
        
        Input: A topic and a list of recommended products with analysis.
        Output: A JSON object containing:
            - "slug": URL-friendly slug.
            - "title": SEO Title.
            - "excerpt": Short summary for the card.
            - "content": Full Markdown article.
        """
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Topic: {topic}\n\nPortfolio Manager Recommendations: {recommendations}\n\nGenerate the full article content in JSON format.")
        ])
        
        self.chain = self.prompt | self.llm | StrOutputParser()

        # --- Plan Generation Chain ---
        self.plan_system_prompt = """
        You are the Product Manager. Create a content plan for a new article.
        
        Topic: {topic}
        Context/Memory: {memory_context}
        Critic Feedback to Address: {critic_feedback}
        Human Feedback to Address: {human_feedback}
        
        Available Products: {products_summary}
        
        Return a JSON object with:
        - "topic": The topic
        - "target_audience": Who is this for?
        - "key_products": List of top 3 product names selected from available products.
        - "angle": The specific angle (e.g., "Best for Students", "2025 Guide").
        - "improvements_made": How you addressed the feedback.
        """
        
        self.plan_prompt = ChatPromptTemplate.from_messages([
            ("system", self.plan_system_prompt),
            ("user", "Create the content plan.")
        ])
        
        self.plan_chain = self.plan_prompt | self.llm | StrOutputParser()

    def create_plan(self, topic, recommendations, critic_feedback="", human_feedback=""):
        print(f"📝 Product Manager planning for: {topic}...")
        
        # Retrieve context
        context = self.memory.retrieve_relevant_context(topic)
        
        # Summarize products for the prompt
        products_summary = json.dumps(recommendations[:5], indent=2) if isinstance(recommendations, list) else str(recommendations)
        
        try:
            response = self.plan_chain.invoke({
                "topic": topic,
                "memory_context": context,
                "critic_feedback": critic_feedback,
                "human_feedback": human_feedback,
                "products_summary": products_summary
            })
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"❌ Error generating plan: {e}")
            # Fallback plan if LLM fails
            return {
                "topic": topic,
                "target_audience": "General",
                "key_products": [],
                "angle": "Guide",
                "improvements_made": "Error in generation"
            }

    def create_content(self, topic, recommendations):
        print(f"✍️ Product Manager writing content for: {topic}...")
        
        # Retrieve context
        context = self.memory.retrieve_relevant_context(topic)
        
        try:
            response = self.chain.invoke({
                "topic": topic, 
                "recommendations": recommendations,
                "memory_context": context
            })
            # Clean up potential markdown code blocks
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            # Remove potential invalid control characters
            cleaned_response = "".join(c for c in cleaned_response if c >= ' ' or c == '\n' or c == '\r' or c == '\t')
            
            return json.loads(cleaned_response, strict=False)
        except Exception as e:
            print(f"❌ Error generating content: {e}")
            print(f"Raw response was: {response[:200]}...") # Debugging aid
            return None

if __name__ == "__main__":
    pm = ProductManagerAgent()
    print("Product Manager Initialized.")
