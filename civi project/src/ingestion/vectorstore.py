import os
import time
import chromadb
from chromadb.config import Settings
from src.config import Config

class VectorStoreManager:
    def __init__(self):
        self.persist_dir = Config.CHROMA_PERSIST_DIR
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # Initialize chromadb persistent client
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # We will use sentence-transformers/all-MiniLM-L6-v2 running locally.
        # This executes on CPU/GPU without external API calls.
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(Config.EMBEDDING_MODEL_NAME)
            self.has_embedder = True
        except ImportError:
            self.has_embedder = False
            print("[Warning] sentence-transformers package not installed. Embeddings cannot be computed.")
            
        # Get or create collection
        self.collection_name = "administrative_procedures"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, chunks):
        """
        chunks: list of dicts:
        {
            "id": str (unique_id),
            "text": str (chunk_text),
            "metadata": dict (e.g. {"code": "1.115729", "section": "trinh_tu", "title": "..."})
        }
        """
        if not self.has_embedder:
            raise RuntimeError("SentenceTransformer embedder is not available. Please install sentence-transformers.")
            
        ids = []
        documents = []
        metadatas = []
        embeddings = []
        
        for idx, chunk in enumerate(chunks):
            # Compute embeddings locally
            embedding = self.embedder.encode(chunk["text"]).tolist()
            
            ids.append(chunk.get("id", f"chunk_{idx}_{time.time()}"))
            documents.append(chunk["text"])
            metadatas.append(chunk["metadata"])
            embeddings.append(embedding)
            
        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.upsert(
                ids=ids[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                documents=documents[i:i+batch_size]
            )
        print(f"Successfully added {len(ids)} document chunks to ChromaDB collection: {self.collection_name}")

    def query(self, query_text, filter_dict=None, n_results=5):
        """
        query_text: search term
        filter_dict: metadata filtering (e.g. {"code": "1.115729"})
        """
        if not self.has_embedder:
            return []
            
        query_embedding = self.embedder.encode(query_text).tolist()
        
        # Prepare filter for ChromaDB
        where_clause = None
        if filter_dict:
            # If multiple filters, format for ChromaDB: {"$and": [...]}
            if len(filter_dict) > 1:
                where_clause = {"$and": [{k: v} for k, v in filter_dict.items()]}
            else:
                where_clause = filter_dict
                
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_clause
        )
        
        # Format results nicely
        formatted_results = []
        if results and 'documents' in results and results['documents']:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            ids = results['ids'][0]
            distances = results['distances'][0] if 'distances' in results else [0]*len(docs)
            
            for d, m, i, dist in zip(docs, metas, ids, distances):
                formatted_results.append({
                    "id": i,
                    "text": d,
                    "metadata": m,
                    "score": 1 - dist  # Cosine similarity score
                })
        return formatted_results
