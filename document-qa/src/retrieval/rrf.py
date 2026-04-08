"""Reciprocal Rank Fusion (RRF) modülü.

Dense ve sparse arama sonuçlarını birleştirmek için kullanılır.
Ayrı, test edilebilir bir modül olarak tasarlanmıştır.

Formül: skor(d) = Σ 1/(k + rank_i)
"""

from src.config import RRF_K


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = RRF_K,
) -> list[tuple[str, float]]:
    """Birden fazla sıralı listeyi RRF ile birleştirir.

    Args:
        ranked_lists: Her biri sıralı ID listesi olan listeler.
            Örn: [["id1", "id2", "id3"], ["id2", "id1", "id4"]]
        k: RRF sabiti (varsayılan 60). Yüksek k değeri
            sıralama farklarını yumuşatır.

    Returns:
        (id, skor) çiftleri listesi, skora göre azalan sırada.
    """
    scores: dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank, doc_id in enumerate(ranked_list, start=1):
            if doc_id not in scores:
                scores[doc_id] = 0.0
            scores[doc_id] += 1.0 / (k + rank)

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results
