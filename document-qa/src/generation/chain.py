"""RAG chain modülü.

Retrieval → Context → LLM → Cevap akışını yöneten
deterministik RAG pipeline. Güvenlik katmanları ve LangSmith izleme dahil.
"""

import logging
from collections.abc import Generator
from dataclasses import dataclass, field

from langsmith import traceable

from src.generation.llm import LLMClient
from src.generation.prompts import build_context, format_prompt
from src.retrieval.hybrid_search import HybridSearcher
from src.retrieval.reranker import Reranker
from src.security.input_guard import check_input
from src.security.document_guard import sanitize_context
from src.security.output_guard import check_output

logger = logging.getLogger(__name__)

NO_CONTEXT_RESPONSE = "Bu konuda yüklenen belgelerde bilgi bulunamadı."
INJECTION_RESPONSE = "Bu soru güvenlik kontrolünden geçemedi. Lütfen belge içeriğiyle ilgili bir soru sorun."
UNSAFE_OUTPUT_RESPONSE = "Cevap güvenlik kontrolünden geçemedi. Lütfen sorunuzu farklı şekilde sorun."


@dataclass
class RAGResponse:
    """RAG pipeline cevap yapısı."""

    answer: str
    sources: list[dict] = field(default_factory=list)
    has_context: bool = True
    is_safe: bool = True
    warnings: list[str] = field(default_factory=list)


class RAGChain:
    """Deterministik RAG pipeline.

    Akış: Input Guard → Hybrid Search → RRF → Reranker →
          Context Sanitize → LLM → Output Guard → Cevap
    """

    def __init__(self) -> None:
        self._searcher = HybridSearcher()
        self._reranker = Reranker()
        self._llm = LLMClient()

    @traceable(name="rag_query", run_type="chain")
    def query(self, question: str) -> RAGResponse:
        """Soruyu RAG pipeline üzerinden yanıtlar (non-streaming).

        Args:
            question: Kullanıcının sorusu.

        Returns:
            RAGResponse: Cevap, kaynaklar ve context durumu.
        """
        # 0. Input guard — prompt injection kontrolü
        input_check = check_input(question)
        if not input_check.is_safe:
            logger.warning("Input guard tetiklendi: %s", input_check.reason)
            return RAGResponse(
                answer=input_check.reason,
                is_safe=False,
            )

        # 1. Hybrid search
        search_results = self._retrieve(question)

        # 2. Reranking
        reranked = self._rerank(question, search_results)

        # 3. Context yok → fallback (halüsinasyon önleme)
        if not reranked:
            logger.info("Soru icin context bulunamadi: '%s'", question[:50])
            return RAGResponse(
                answer=NO_CONTEXT_RESPONSE,
                has_context=False,
            )

        # 4. Context oluştur + indirect injection temizleme
        context = build_context(reranked)
        context = sanitize_context(context)
        prompt = format_prompt(context, question)

        # 5. LLM cevap üret
        answer = self._generate(prompt)

        # 6. Output guard — çıktı doğrulama
        output_check = check_output(answer, context)
        warnings = output_check.warnings

        if not output_check.is_safe:
            logger.warning("Output guard tetiklendi: %s", warnings)
            return RAGResponse(
                answer=UNSAFE_OUTPUT_RESPONSE,
                is_safe=False,
                warnings=warnings,
            )

        # 7. Kaynak bilgilerini topla
        sources = self._extract_sources(reranked)

        logger.info(
            "RAG cevap uretildi: '%s' -> %d kaynak",
            question[:50],
            len(sources),
        )
        return RAGResponse(
            answer=answer,
            sources=sources,
            has_context=True,
            warnings=warnings,
        )

    @traceable(name="rag_query_stream", run_type="chain")
    def query_stream(
        self, question: str
    ) -> tuple[Generator[str, None, None] | None, list[dict], bool, list[str]]:
        """Soruyu RAG pipeline üzerinden yanıtlar (streaming).

        Args:
            question: Kullanıcının sorusu.

        Returns:
            Tuple of:
                - Token generator (None ise context yok veya güvensiz)
                - Kaynak listesi
                - has_context flag
                - Uyarı listesi
        """
        # 0. Input guard
        input_check = check_input(question)
        if not input_check.is_safe:
            logger.warning("Input guard tetiklendi: %s", input_check.reason)
            return None, [], False, [input_check.reason]

        # 1. Hybrid search
        search_results = self._retrieve(question)

        # 2. Reranking
        reranked = self._rerank(question, search_results)

        # 3. Context yok → fallback
        if not reranked:
            logger.info("Soru icin context bulunamadi: '%s'", question[:50])
            return None, [], False, []

        # 4. Context oluştur + sanitize
        context = build_context(reranked)
        context = sanitize_context(context)
        prompt = format_prompt(context, question)

        # 5. Kaynak bilgilerini topla
        sources = self._extract_sources(reranked)

        # 6. Streaming generator döndür
        return self._llm.generate_stream(prompt), sources, True, []

    @traceable(name="hybrid_search", run_type="retriever")
    def _retrieve(self, question: str) -> list[dict]:
        """Hybrid search wrapper (LangSmith trace)."""
        return self._searcher.search(question)

    @traceable(name="rerank", run_type="chain")
    def _rerank(self, question: str, search_results: list[dict]) -> list[dict]:
        """Reranker wrapper (LangSmith trace)."""
        return self._reranker.rerank(question, search_results)

    @traceable(name="llm_generate", run_type="llm")
    def _generate(self, prompt: str) -> str:
        """LLM generate wrapper (LangSmith trace)."""
        return self._llm.generate(prompt)

    def _extract_sources(self, reranked: list[dict]) -> list[dict]:
        """Reranked sonuçlardan kaynak bilgilerini çıkarır."""
        return [
            {
                "source_file": r.get("metadata", {}).get("source_file", ""),
                "page_number": r.get("metadata", {}).get("page_number", ""),
                "rerank_score": r.get("rerank_score", 0.0),
            }
            for r in reranked
        ]
