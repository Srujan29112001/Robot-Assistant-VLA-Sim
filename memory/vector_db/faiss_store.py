"""
FAISS Vector Database for Semantic Memory
Efficient similarity search for episodic robot memory
"""

import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """
    FAISS-based vector database for robot episodic memory
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        dimension: int = 384,
        index_type: str = "Flat",  # "Flat", "IVF", "HNSW"
        metric: str = "L2",  # "L2" or "IP" (inner product)
        persist_directory: str = "./vector_db"
    ):
        self.dimension = dimension
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedder = SentenceTransformer(embedding_model)

        # Create FAISS index
        self.index = self._create_index(index_type, metric)

        # Metadata store (maps vector ID to document metadata)
        self.metadata_store: List[Dict[str, Any]] = []

        # ID mapping
        self.id_counter = 0

        logger.info(f"FAISS Vector Store initialized: {index_type}, dim={dimension}")

    def _create_index(self, index_type: str, metric: str) -> faiss.Index:
        """Create FAISS index based on type"""

        if metric == "IP":
            if index_type == "Flat":
                index = faiss.IndexFlatIP(self.dimension)
            elif index_type == "IVF":
                quantizer = faiss.IndexFlatIP(self.dimension)
                index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            elif index_type == "HNSW":
                index = faiss.IndexHNSWFlat(self.dimension, 32)
            else:
                raise ValueError(f"Unknown index type: {index_type}")
        else:  # L2
            if index_type == "Flat":
                index = faiss.IndexFlatL2(self.dimension)
            elif index_type == "IVF":
                quantizer = faiss.IndexFlatL2(self.dimension)
                index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            elif index_type == "HNSW":
                index = faiss.IndexHNSWFlat(self.dimension, 32)
            else:
                raise ValueError(f"Unknown index type: {index_type}")

        return index

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for text

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        embedding = self.embedder.encode(text, convert_to_numpy=True)
        return embedding.astype('float32')

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Batch embed multiple texts"""
        embeddings = self.embedder.encode(texts, convert_to_numpy=True)
        return embeddings.astype('float32')

    def add(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[np.ndarray] = None
    ) -> int:
        """
        Add document to vector store

        Args:
            text: Document text
            metadata: Associated metadata
            embedding: Pre-computed embedding (optional)

        Returns:
            Document ID
        """
        # Generate embedding if not provided
        if embedding is None:
            embedding = self.embed_text(text)

        # Ensure correct shape
        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)

        # Add to FAISS index
        self.index.add(embedding)

        # Store metadata
        doc_id = self.id_counter
        self.id_counter += 1

        meta = metadata or {}
        meta.update({
            'id': doc_id,
            'text': text,
            'timestamp': datetime.now().isoformat()
        })
        self.metadata_store.append(meta)

        logger.debug(f"Added document {doc_id} to vector store")
        return doc_id

    def add_batch(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[int]:
        """
        Add multiple documents in batch

        Args:
            texts: List of documents
            metadatas: List of metadata dicts

        Returns:
            List of document IDs
        """
        # Generate embeddings
        embeddings = self.embed_texts(texts)

        # Add to index
        self.index.add(embeddings)

        # Store metadata
        ids = []
        for i, text in enumerate(texts):
            doc_id = self.id_counter
            self.id_counter += 1
            ids.append(doc_id)

            meta = metadatas[i] if metadatas else {}
            meta.update({
                'id': doc_id,
                'text': text,
                'timestamp': datetime.now().isoformat()
            })
            self.metadata_store.append(meta)

        logger.info(f"Added {len(texts)} documents to vector store")
        return ids

    def search(
        self,
        query: str,
        k: int = 5,
        filter_fn: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for similar documents

        Args:
            query: Search query
            k: Number of results
            filter_fn: Optional filter function for metadata

        Returns:
            List of results with text, metadata, and scores
        """
        # Generate query embedding
        query_embedding = self.embed_text(query)
        query_embedding = query_embedding.reshape(1, -1)

        # Search in FAISS
        distances, indices = self.index.search(query_embedding, k * 2)  # Get more for filtering

        # Retrieve results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata_store):
                metadata = self.metadata_store[idx]

                # Apply filter if provided
                if filter_fn and not filter_fn(metadata):
                    continue

                result = metadata.copy()
                result['score'] = float(1.0 / (1.0 + dist))  # Convert distance to similarity
                result['distance'] = float(dist)
                results.append(result)

                if len(results) >= k:
                    break

        logger.debug(f"Found {len(results)} results for query: {query[:50]}...")
        return results

    def search_by_embedding(
        self,
        embedding: np.ndarray,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search using pre-computed embedding"""
        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)

        distances, indices = self.index.search(embedding, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata_store):
                metadata = self.metadata_store[idx]
                result = metadata.copy()
                result['score'] = float(1.0 / (1.0 + dist))
                result['distance'] = float(dist)
                results.append(result)

        return results

    def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve document by ID"""
        for meta in self.metadata_store:
            if meta.get('id') == doc_id:
                return meta
        return None

    def delete(self, doc_id: int):
        """
        Delete document (marks as deleted, FAISS doesn't support true deletion)
        """
        for i, meta in enumerate(self.metadata_store):
            if meta.get('id') == doc_id:
                self.metadata_store[i]['deleted'] = True
                logger.debug(f"Marked document {doc_id} as deleted")
                return
        logger.warning(f"Document {doc_id} not found for deletion")

    def save(self):
        """Persist index and metadata to disk"""
        # Save FAISS index
        faiss.write_index(self.index, str(self.persist_dir / "index.faiss"))

        # Save metadata
        with open(self.persist_dir / "metadata.pkl", 'wb') as f:
            pickle.dump({
                'metadata_store': self.metadata_store,
                'id_counter': self.id_counter
            }, f)

        logger.info(f"Vector store saved to {self.persist_dir}")

    def load(self):
        """Load index and metadata from disk"""
        index_path = self.persist_dir / "index.faiss"
        metadata_path = self.persist_dir / "metadata.pkl"

        if index_path.exists():
            self.index = faiss.read_index(str(index_path))

        if metadata_path.exists():
            with open(metadata_path, 'rb') as f:
                data = pickle.load(f)
                self.metadata_store = data['metadata_store']
                self.id_counter = data['id_counter']

            logger.info(f"Vector store loaded from {self.persist_dir}")
        else:
            logger.warning("No existing vector store found")

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        return {
            'total_documents': len(self.metadata_store),
            'index_size': self.index.ntotal,
            'dimension': self.dimension,
            'is_trained': self.index.is_trained if hasattr(self.index, 'is_trained') else True
        }


# Example usage
if __name__ == "__main__":
    # Initialize vector store
    vs = FAISSVectorStore()

    # Add some robot memories
    memories = [
        "I saw a red bottle on the left table in the kitchen at 10 AM",
        "The user asked me to fetch the blue cup from the living room",
        "I detected a person standing near the doorway",
        "Battery level dropped to 20% during navigation to bedroom",
        "Successfully grasped the mug using adaptive grip control",
    ]

    metadatas = [
        {"type": "observation", "location": "kitchen", "objects": ["bottle"]},
        {"type": "command", "location": "living_room", "objects": ["cup"]},
        {"type": "detection", "location": "entrance", "entities": ["person"]},
        {"type": "status", "battery": 20},
        {"type": "action", "success": True, "object": "mug"},
    ]

    # Add to store
    vs.add_batch(memories, metadatas)

    # Search
    results = vs.search("Where is the bottle?", k=2)

    print("Search Results:")
    for r in results:
        print(f"  Score: {r['score']:.3f} - {r['text']}")
        print(f"  Metadata: {r.get('type')}, {r.get('location')}")

    # Save
    vs.save()

    print(f"\nStats: {vs.get_stats()}")
