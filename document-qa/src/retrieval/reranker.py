"""Reranker modülü.

BGE-Reranker-v2-m3 cross-encoder ile hybrid search sonuçlarını
yeniden sıralayarak en alakalı chunk'ları seçer.
top_k sonuçtan top_n sonuç döndürür.
"""

import logging

from FlagEmbedding import FlagReranker

from src.config import RERANK_SCORE_THRESHOLD, RERANK_TOP_N, RERANKER_MODEL

logger = logging.getLogger(__name__)


class Reranker:
    """BGE-Reranker cross-encoder tabanlı yeniden sıralama.

    Lazy loading: Model ilk kullanımda yüklenir.
    """

    def __init__(self) -> None:
        self._model: FlagReranker | None = None

    def _get_model(self) -> FlagReranker:
        """Reranker modelini lazy olarak yükler."""
        if self._model is None:
            logger.info("Reranker modeli yukleniyor: %s", RERANKER_MODEL)
            self._model = FlagReranker(RERANKER_MODEL, use_fp16=True)
            logger.info("Reranker modeli yuklendi.")
        return self._model

    def rerank(
        self,
        query: str,
        search_results: list[dict],
        top_n: int = RERANK_TOP_N,
        score_threshold: float = RERANK_SCORE_THRESHOLD,
    ) -> list[dict]:
        """Arama sonuçlarını cross-encoder ile yeniden sıralar.

        Args:
            query: Kullanıcı sorusu.
            search_results: Hybrid search sonuçları.
                Her biri {"id", "text", "score", "metadata"} içerir.
            top_n: Döndürülecek maksimum sonuç sayısı.
            score_threshold: Minimum reranker skoru.

        Returns:
            Yeniden sıralanmış ve filtrelenmiş sonuç listesi.
            Her sonuca "rerank_score" eklenir.
        """
        if not search_results:
            return []

        model = self._get_model()

        # Soru-chunk çiftleri oluştur
        pairs = [[query, result["text"]] for result in search_results]

        # Cross-encoder skorları hesapla
        scores = model.compute_score(pairs, normalize=True)

        # Tek sonuç gelirse liste yap
        if isinstance(scores, float):
            scores = [scores]

        # Sonuçlara rerank skoru ekle
        for i, result in enumerate(search_results):
            result["rerank_score"] = scores[i]

        # Eşik üstü filtrele ve sırala
        filtered = [
            r for r in search_results if r["rerank_score"] >= score_threshold
        ]
        filtered.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Top N al
        top_results = filtered[:top_n]

        logger.info(
            "Reranking tamamlandi: %d sonuc -> %d sonuc (threshold: %.2f)",
            len(search_results),
            len(top_results),
            score_threshold,
        )
        return top_results
