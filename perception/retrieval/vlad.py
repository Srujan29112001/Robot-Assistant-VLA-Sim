"""
VLAD (Vector of Locally Aggregated Descriptors) for Visual Place Recognition
Used for object re-identification and visual memory retrieval
"""

import torch
import torch.nn as nn
import numpy as np
from typing import List, Dict, Tuple
from PIL import Image
import faiss
import pickle
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VLADEncoder(nn.Module):
    """
    VLAD encoding layer
    Aggregates local CNN features into compact global descriptor
    """

    def __init__(self, feature_dim: int = 512, num_clusters: int = 64):
        super().__init__()
        self.feature_dim = feature_dim
        self.num_clusters = num_clusters

        # Learnable cluster centers
        self.cluster_centers = nn.Parameter(
            torch.randn(num_clusters, feature_dim)
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """
        Encode local features to VLAD descriptor

        Args:
            features: Local features [B, N, D] where N is number of patches

        Returns:
            VLAD descriptor [B, K*D] where K is num_clusters
        """
        B, N, D = features.shape

        # Compute soft assignment to clusters
        # [B, N, K]
        assignment = torch.softmax(
            -torch.cdist(features, self.cluster_centers.unsqueeze(0).expand(B, -1, -1)),
            dim=-1
        )

        # Compute residuals: feature - assigned_cluster
        # [B, N, K, D]
        residuals = features.unsqueeze(2) - self.cluster_centers.unsqueeze(0).unsqueeze(0)

        # Weight residuals by soft assignment and sum
        # [B, K, D]
        vlad = torch.sum(assignment.unsqueeze(-1) * residuals, dim=1)

        # Flatten and L2 normalize
        vlad = vlad.view(B, -1)
        vlad = torch.nn.functional.normalize(vlad, p=2, dim=-1)

        return vlad


class VLADRetrieval:
    """
    VLAD-based visual retrieval system for robot memory
    """

    def __init__(
        self,
        feature_dim: int = 512,
        num_clusters: int = 64,
        index_path: str = None,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        self.device = torch.device(device)
        self.feature_dim = feature_dim

        # VLAD encoder
        self.vlad_encoder = VLADEncoder(feature_dim, num_clusters).to(self.device)

        # FAISS index for fast retrieval
        descriptor_dim = feature_dim * num_clusters
        self.index = faiss.IndexFlatL2(descriptor_dim)

        # Memory store: image metadata
        self.memory_store = []

        # Load existing index if provided
        if index_path and Path(index_path).exists():
            self.load(index_path)

        logger.info(f"VLAD Retrieval initialized: dim={descriptor_dim}, clusters={num_clusters}")

    def extract_vlad(self, features: torch.Tensor) -> np.ndarray:
        """
        Extract VLAD descriptor from CNN features

        Args:
            features: Local features [N, D]

        Returns:
            VLAD descriptor
        """
        self.vlad_encoder.eval()
        with torch.no_grad():
            features = features.unsqueeze(0).to(self.device)  # [1, N, D]
            vlad = self.vlad_encoder(features)
            return vlad.cpu().numpy()

    def add_to_index(
        self,
        features: torch.Tensor,
        metadata: Dict
    ) -> int:
        """
        Add image to retrieval index

        Args:
            features: Local CNN features [N, D]
            metadata: Associated metadata (image_path, timestamp, location, etc.)

        Returns:
            Index ID
        """
        # Extract VLAD descriptor
        vlad = self.extract_vlad(features)

        # Add to FAISS index
        self.index.add(vlad)

        # Store metadata
        idx = len(self.memory_store)
        self.memory_store.append(metadata)

        logger.debug(f"Added image {idx} to index: {metadata.get('location', 'unknown')}")
        return idx

    def retrieve(
        self,
        query_features: torch.Tensor,
        k: int = 5,
        threshold: float = None
    ) -> List[Dict]:
        """
        Retrieve similar images from memory

        Args:
            query_features: Query image features [N, D]
            k: Number of results to return
            threshold: Distance threshold (optional)

        Returns:
            List of retrieved results with metadata and scores
        """
        # Extract query VLAD
        query_vlad = self.extract_vlad(query_features)

        # Search in FAISS index
        distances, indices = self.index.search(query_vlad, k)

        # Filter by threshold if provided
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if threshold is None or dist < threshold:
                if idx < len(self.memory_store):
                    result = self.memory_store[idx].copy()
                    result['distance'] = float(dist)
                    result['similarity'] = float(1.0 / (1.0 + dist))
                    results.append(result)

        logger.info(f"Retrieved {len(results)} matches for query")
        return results

    def recognize_place(
        self,
        query_features: torch.Tensor,
        threshold: float = 0.3
    ) -> Tuple[bool, str, float]:
        """
        Recognize if current view matches a known place

        Args:
            query_features: Current image features
            threshold: Recognition threshold

        Returns:
            (recognized, location_name, confidence)
        """
        results = self.retrieve(query_features, k=1, threshold=threshold)

        if results:
            best_match = results[0]
            location = best_match.get('location', 'unknown')
            confidence = best_match['similarity']
            return True, location, confidence
        else:
            return False, None, 0.0

    def save(self, path: str):
        """Save VLAD index and memory"""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, str(save_path / "vlad.index"))

        # Save memory store
        with open(save_path / "memory.pkl", 'wb') as f:
            pickle.dump(self.memory_store, f)

        # Save encoder weights
        torch.save(
            self.vlad_encoder.state_dict(),
            save_path / "vlad_encoder.pth"
        )

        logger.info(f"VLAD system saved to {path}")

    def load(self, path: str):
        """Load VLAD index and memory"""
        load_path = Path(path)

        # Load FAISS index
        self.index = faiss.read_index(str(load_path / "vlad.index"))

        # Load memory store
        with open(load_path / "memory.pkl", 'rb') as f:
            self.memory_store = pickle.load(f)

        # Load encoder weights
        self.vlad_encoder.load_state_dict(
            torch.load(load_path / "vlad_encoder.pth", map_location=self.device)
        )

        logger.info(f"VLAD system loaded from {path}")


# Example usage
if __name__ == "__main__":
    # Initialize VLAD retrieval
    vlad = VLADRetrieval(feature_dim=512, num_clusters=64)

    # Simulate adding images to memory
    for i in range(10):
        # Dummy features
        features = torch.randn(196, 512)  # 14x14 patches, 512-dim features

        metadata = {
            'image_id': f'img_{i}',
            'location': f'room_{i % 3}',
            'timestamp': '2025-01-01 12:00:00',
            'objects': ['bottle', 'cup']
        }

        vlad.add_to_index(features, metadata)

    # Query
    query_features = torch.randn(196, 512)
    results = vlad.retrieve(query_features, k=3)

    print(f"Retrieved {len(results)} results:")
    for r in results:
        print(f"  - {r['location']}: similarity={r['similarity']:.3f}")

    # Place recognition
    recognized, location, confidence = vlad.recognize_place(query_features)
    print(f"Recognized: {recognized}, Location: {location}, Confidence: {confidence:.3f}")
