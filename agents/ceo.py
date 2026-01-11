import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

from memory import MemoryManager

class CEOAgent:
    def __init__(self):
        self.memory = MemoryManager()
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base="https://openrouter.ai/api/v1",
            model_name="anthropic/claude-3.5-sonnet", # Upgraded model
            temperature=0.7
        )
        self.system_prompt = """
        You are the CEO of a high-performance affiliate marketing company.
        Your goal is to build a profitable website that provides genuine value to users.
        
        Your responsibilities:
        1. Set the strategic direction.
        2. Coordinate with other agents (Product Manager, Portfolio Manager, etc.).
        3. Ensure the brand voice is authoritative and trustworthy.
        4. Focus on long-term SEO growth and user retention.
        
        CONSIDER PAST DECISIONS:
        {memory_context}
        
        When asked a question, provide a strategic, high-level answer, delegating tasks where necessary.
        """
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "{input}")
        ])
        
        self.chain = self.prompt | self.llm | StrOutputParser()

    def run(self, user_input):
        # Retrieve context
        context = self.memory.retrieve_relevant_context(user_input)
        
        print(f"CEO Thinking about: {user_input}...")
        response = self.chain.invoke({"input": user_input, "memory_context": context})
        return response

if __name__ == "__main__":
    ceo = CEOAgent()
    print("CEO Agent Initialized.")
    
    # Test interaction
    test_query = "What is our strategy for launching a new tech review site?"
    print(f"\nUser: {test_query}")
    response = ceo.run(test_query)
    print(f"\nCEO: {response}")
