"""Embedding ve Qdrant indeksleme modülü.

BGE-M3 modeli ile dense + sparse vektör üretir ve
Qdrant vektör veritabanına yazar. Lazy loading ile model
sadece ilk kullanımda yüklenir.
"""

import logging
import uuid

from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    NamedSparseVector,
    NamedVector,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from src.config import EMBEDDING_MODEL, QDRANT_COLLECTION, QDRANT_URL
from src.document_processing.smart_loader import DocumentChunk

logger = logging.getLogger(__name__)

DENSE_DIM = 1024  # BGE-M3 dense vector boyutu


class Embedder:
    """BGE-M3 embedding + Qdrant yazma.

    Lazy loading: BGE-M3 modeli ve Qdrant client ilk kullanımda yüklenir.
    """

    def __init__(self) -> None:
        self._model: BGEM3FlagModel | None = None
        self._client: QdrantClient | None = None

    def _get_model(self) -> BGEM3FlagModel:
        """BGE-M3 modelini lazy olarak yükler."""
        if self._model is None:
            logger.info("BGE-M3 modeli yukleniyor: %s", EMBEDDING_MODEL)
            self._model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=True)
            logger.info("BGE-M3 modeli yuklendi.")
        return self._model

    def _get_client(self) -> QdrantClient:
        """Qdrant client'ı lazy olarak oluşturur."""
        if self._client is None:
            self._client = QdrantClient(url=QDRANT_URL)
            logger.info("Qdrant baglantisi kuruldu: %s", QDRANT_URL)
        return self._client

    def ensure_collection(self) -> None:
        """Qdrant collection'ı yoksa oluşturur (dense + sparse)."""
        client = self._get_client()

        collections = [c.name for c in client.get_collections().collections]
        if QDRANT_COLLECTION in collections:
            logger.info("Collection zaten mevcut: %s", QDRANT_COLLECTION)
            return

        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config={
                "dense": VectorParams(size=DENSE_DIM, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(index=SparseIndexParams()),
            },
        )
        logger.info("Collection olusturuldu: %s", QDRANT_COLLECTION)

    def embed_and_index(self, chunks: list[DocumentChunk]) -> int:
        """Chunk'ları embed eder ve Qdrant'a yazar.

        Args:
            chunks: Embed edilecek chunk listesi.

        Returns:
            Qdrant'a yazılan nokta sayısı.
        """
        if not chunks:
            logger.warning("Bos chunk listesi, indeksleme yapilmadi.")
            return 0

        self.ensure_collection()

        model = self._get_model()
        texts = [chunk.text for chunk in chunks]

        logger.info("Embedding hesaplaniyor: %d chunk", len(texts))
        output = model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )

        dense_vectors = output["dense_vecs"]
        sparse_weights = output["lexical_weights"]

        points: list[PointStruct] = []
        for i, chunk in enumerate(chunks):
            sparse_dict = sparse_weights[i]
            sparse_indices = list(sparse_dict.keys())
            sparse_values = list(sparse_dict.values())

            point = PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": dense_vectors[i].tolist(),
                },
                payload={
                    "text": chunk.text,
                    **chunk.metadata,
                },
            )
            # Sparse vector'ü ayrı ekle
            point.vector["sparse"] = SparseVector(
                indices=sparse_indices,
                values=sparse_values,
            )
            points.append(point)

        client = self._get_client()
        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points,
        )

        logger.info(
            "Indeksleme tamamlandi: %d chunk -> Qdrant '%s'",
            len(points),
            QDRANT_COLLECTION,
        )
        return len(points)

    def delete_collection(self) -> None:
        """Mevcut collection'ı siler (yeniden indeksleme için)."""
        client = self._get_client()
        client.delete_collection(collection_name=QDRANT_COLLECTION)
        logger.info("Collection silindi: %s", QDRANT_COLLECTION)
