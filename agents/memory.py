import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

class MemoryManager:
    def __init__(self, persist_directory="./memory_db"):
        self.persist_directory = persist_directory
        
        # Use a lightweight, high-quality local embedding model
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        self.vector_store = Chroma(
            collection_name="affiliate_decisions",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )

    def add_decision(self, topic, decision, agent_role, rationale=""):
        """Stores a decision in the vector database."""
        doc = Document(
            page_content=f"Topic: {topic}\nDecision: {decision}\nRationale: {rationale}",
            metadata={
                "topic": topic,
                "agent": agent_role,
                "timestamp": str(os.path.getmtime(self.persist_directory) if os.path.exists(self.persist_directory) else 0) # Placeholder timestamp
            }
        )
        self.vector_store.add_documents([doc])
        print(f"💾 Memory: Saved decision for '{topic}' by {agent_role}.")

    def retrieve_relevant_context(self, query, k=3):
        """Retrieves relevant past decisions."""
        results = self.vector_store.similarity_search(query, k=k)
        if not results:
            return ""
        
        context_str = "\n".join([f"- {doc.page_content}" for doc in results])
        return f"Relevant Past Decisions:\n{context_str}\n"

if __name__ == "__main__":
    # Test
    mem = MemoryManager()
    mem.add_decision("notebooks", "Focus on battery life for business users", "CEO")
    print(mem.retrieve_relevant_context("laptop strategy"))
