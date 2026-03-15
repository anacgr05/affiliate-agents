import os
import logging
import threading

logger = logging.getLogger(__name__)

# Memory is DISABLED by default to avoid loading HuggingFace models (~90MB)
# which cause GIL starvation and block the uvicorn event loop.
# Enable with ENABLE_MEMORY=1 environment variable.
MEMORY_ENABLED = os.getenv("ENABLE_MEMORY", "0") == "1"


class MemoryManager:
    """Singleton — the HuggingFace model is loaded once and reused.

    Disabled by default (ENABLE_MEMORY=0). When disabled, all methods
    are no-ops that return empty results. This avoids loading torch,
    transformers, and the all-MiniLM-L6-v2 model (~90MB) which causes
    GIL starvation and blocks HTTP responses.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, persist_directory="./memory_db"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, persist_directory="./memory_db"):
        if self._initialized:
            return
        self._initialized = True
        self.persist_directory = persist_directory

        if not MEMORY_ENABLED:
            logger.info("🧠 MemoryManager disabled (ENABLE_MEMORY=0)")
            self.embeddings = None
            self.vector_store = None
            return

        # Heavy imports — only when memory is enabled
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings

        logger.info("🧠 MemoryManager: Loading HuggingFace embeddings...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        self.vector_store = Chroma(
            collection_name="affiliate_decisions",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
        )
        logger.info("🧠 MemoryManager: Ready")

    def add_decision(self, topic, decision, agent_role, rationale=""):
        """Stores a decision in the vector database (thread-safe)."""
        if not MEMORY_ENABLED or self.vector_store is None:
            return

        from langchain_core.documents import Document

        doc = Document(
            page_content=f"Topic: {topic}\nDecision: {decision}\nRationale: {rationale}",
            metadata={
                "topic": topic,
                "agent": agent_role,
                "timestamp": str(
                    os.path.getmtime(self.persist_directory)
                    if os.path.exists(self.persist_directory)
                    else 0
                ),
            },
        )
        with self._lock:
            self.vector_store.add_documents([doc])
        logger.info(f"💾 Memory: Saved decision for '{topic}' by {agent_role}.")

    def retrieve_relevant_context(self, query, k=3):
        """Retrieves relevant past decisions (thread-safe)."""
        if not MEMORY_ENABLED or self.vector_store is None:
            return ""

        with self._lock:
            results = self.vector_store.similarity_search(query, k=k)
        if not results:
            return ""

        context_str = "\n".join([f"- {doc.page_content}" for doc in results])
        return f"Relevant Past Decisions:\n{context_str}\n"


if __name__ == "__main__":
    os.environ["ENABLE_MEMORY"] = "1"
    mem = MemoryManager()
    mem.add_decision("notebooks", "Focus on battery life for business users", "CEO")
    print(mem.retrieve_relevant_context("laptop strategy"))
