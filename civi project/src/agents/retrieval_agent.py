from src.ingestion.vectorstore import VectorStoreManager

class RetrievalAgent:
    def __init__(self):
        self.vectorstore = VectorStoreManager()

    def run(self, state):
        query = state.get("query", "")
        selected_proc = state.get("selected_procedure", {})
        
        filter_dict = None
        if selected_proc and "code" in selected_proc:
            # We restrict RAG query to only chunks from the selected procedure code
            filter_dict = {"code": selected_proc["code"]}
            
        print(f"[RAG] Querying vector store for '{query}' with filters: {filter_dict}...")
        results = self.vectorstore.query(query, filter_dict=filter_dict, n_results=5)
        
        # If no results found with filters, perform a fallback query without procedure code restriction
        # to find semantic matches elsewhere
        if not results and filter_dict:
            print(f"[RAG] No filtered results. Performing fallback query without procedure code limit...")
            results = self.vectorstore.query(query, n_results=5)
            
        return {
            "retrieval_results": results
        }
