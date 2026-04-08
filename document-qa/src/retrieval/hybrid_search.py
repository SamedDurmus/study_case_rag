"""Hybrid search modülü.

BGE-M3 ile dense + sparse arama yaparak sonuçları RRF ile birleştirir.
Qdrant üzerinde dense ve sparse sorgu çalıştırır.
"""

import logging

from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from qdrant_client.models import (
    NamedSparseVector,
    NamedVector,
    SparseVector,
    QueryRequest,
)

from src.config import (
    EMBEDDING_MODEL,
    QDRANT_COLLECTION,
    QDRANT_URL,
    RETRIEVAL_TOP_K,
)
from src.retrieval.rrf import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


class HybridSearcher:
    """Dense + Sparse hybrid arama motoru.

    BGE-M3'ün tek encode çağrısıyla ürettiği dense ve sparse
    vektörleri kullanarak Qdrant'ta arama yapar.
    """

    def __init__(self) -> None:
        self._model: BGEM3FlagModel | None = None
        self._client: QdrantClient | None = None

    def _get_model(self) -> BGEM3FlagModel:
        """BGE-M3 modelini lazy olarak yükler."""
        if self._model is None:
            logger.info("BGE-M3 modeli yukleniyor (search)...")
            self._model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=True)
            logger.info("BGE-M3 modeli yuklendi (search).")
        return self._model

    def _get_client(self) -> QdrantClient:
        """Qdrant client'ı lazy olarak oluşturur."""
        if self._client is None:
            self._client = QdrantClient(url=QDRANT_URL)
        return self._client

    def set_model(self, model: BGEM3FlagModel) -> None:
        """Dışarıdan model atamak için (embedder ile paylaşım).

        Args:
            model: Paylaşılacak BGE-M3 model instance'ı.
        """
        self._model = model

    def search(
        self,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
    ) -> list[dict]:
        """Hybrid search: dense + sparse arama + RRF birleştirme.

        Args:
            query: Kullanıcı sorusu.
            top_k: Her arama türünden döndürülecek sonuç sayısı.

        Returns:
            RRF sıralamasına göre sonuç listesi.
            Her sonuç: {"id": str, "text": str, "score": float, "metadata": dict}
        """
        model = self._get_model()
        client = self._get_client()

        # Sorguyu encode et (dense + sparse tek çağrıda)
        query_output = model.encode(
            [query],
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vector = query_output["dense_vecs"][0].tolist()
        sparse_dict = query_output["lexical_weights"][0]
        sparse_indices = list(sparse_dict.keys())
        sparse_values = list(sparse_dict.values())

        # Dense search
        dense_results = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=dense_vector,
            using="dense",
            limit=top_k,
            with_payload=True,
        ).points

        # Sparse search
        sparse_query = SparseVector(
            indices=sparse_indices,
            values=sparse_values,
        )
        sparse_results = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=sparse_query,
            using="sparse",
            limit=top_k,
            with_payload=True,
        ).points

        # RRF birleştirme
        dense_ids = [str(r.id) for r in dense_results]
        sparse_ids = [str(r.id) for r in sparse_results]

        rrf_results = reciprocal_rank_fusion([dense_ids, sparse_ids])

        # ID → payload mapping oluştur
        all_results = {str(r.id): r for r in dense_results}
        for r in sparse_results:
            if str(r.id) not in all_results:
                all_results[str(r.id)] = r

        # RRF sırasında sonuçları döndür
        search_results: list[dict] = []
        for doc_id, rrf_score in rrf_results:
            if doc_id in all_results:
                point = all_results[doc_id]
                search_results.append({
                    "id": doc_id,
                    "text": point.payload.get("text", ""),
                    "score": rrf_score,
                    "metadata": {
                        k: v for k, v in point.payload.items() if k != "text"
                    },
                })

        logger.info(
            "Hybrid search tamamlandi: '%s' -> %d sonuc (dense: %d, sparse: %d)",
            query[:50],
            len(search_results),
            len(dense_results),
            len(sparse_results),
        )
        return search_results
