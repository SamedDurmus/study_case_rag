"""RAGAS değerlendirme scripti.

perio_qa_pairs.json'daki soru-cevap çiftlerini RAG pipeline üzerinden
çalıştırır, RAGAS metrikleriyle değerlendirir ve sonuçları Excel'e yazar.

İki aşamalı çalışır (bellek optimizasyonu):
  Aşama 1: RAG cevapları üret (BGE-M3 + Reranker GPU'da)
  Aşama 2: Modelleri bellekten at → RAGAS değerlendirmesi (Ollama LLM)

Kullanım:
    docker compose exec app python run_evaluation.py
"""

import gc
import json
import logging
import time
from pathlib import Path

import pandas as pd
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QA_PAIRS_PATH = Path("data/test_documents/perio_qa_pairs.json")
OUTPUT_PATH = Path("data/ragas_results.xlsx")


def phase1_rag_responses() -> list[dict]:
    """Aşama 1: RAG pipeline ile cevaplar üret."""
    from src.generation.chain import RAGChain
    from src.retrieval.reranker import Reranker

    with open(QA_PAIRS_PATH, encoding="utf-8") as f:
        qa_pairs = json.load(f)

    logger.info("=== ASAMA 1: RAG CEVAPLARI ===")
    logger.info("Toplam %d soru-cevap cifti yuklendi.", len(qa_pairs))

    chain = RAGChain()
    reranker = Reranker()

    results: list[dict] = []
    for i, qa in enumerate(qa_pairs):
        question = qa["soru"]
        ground_truth = qa["dogru_cevap"]

        logger.info("[%d/%d] Soru: %s", i + 1, len(qa_pairs), question[:60])
        start = time.time()

        # RAG cevabı
        response = chain.query(question)
        elapsed = time.time() - start

        # Context'leri topla
        contexts = []
        if response.has_context:
            search_results = chain._searcher.search(question)
            reranked = reranker.rerank(question, search_results)
            contexts = [r["text"] for r in reranked]

        results.append({
            "soru": question,
            "dogru_cevap": ground_truth,
            "sistem_cevabi": response.answer,
            "contexts": contexts,
            "kaynak": qa.get("kaynak", ""),
            "sources": response.sources,
            "has_context": response.has_context,
            "sure_sn": round(elapsed, 2),
        })

        logger.info(
            "  Cevap: %s... (%.1f sn)",
            response.answer[:80],
            elapsed,
        )

    # Modelleri bellekten at
    logger.info("Retrieval modelleri bellekten cikartiliyor...")
    del chain
    del reranker
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("GPU bellek temizlendi.")

    return results


def phase2_ragas_evaluation(results: list[dict]) -> None:
    """Aşama 2: RAGAS metrikleriyle değerlendir ve Excel'e yaz."""
    from ragas import evaluate
    from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        Faithfulness,
        ResponseRelevancy,
        LLMContextPrecisionWithoutReference,
        LLMContextRecall,
    )
    from langchain_community.chat_models import ChatOllama
    from langchain_community.embeddings import HuggingFaceBgeEmbeddings

    from src.config import EMBEDDING_MODEL, OLLAMA_BASE_URL, OLLAMA_MODEL

    logger.info("=== ASAMA 2: RAGAS DEGERLENDIRMESI ===")

    # LLM ve embedding wrapper
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.0,
        timeout=300,  # 5 dakika — lokal 7B model yavaş
    )
    ragas_llm = LangchainLLMWrapper(llm)

    embeddings = HuggingFaceBgeEmbeddings(model_name=EMBEDDING_MODEL)
    ragas_embeddings = LangchainEmbeddingsWrapper(embeddings)

    # RAGAS dataset oluştur
    eval_samples = []
    for r in results:
        eval_samples.append(
            SingleTurnSample(
                user_input=r["soru"],
                response=r["sistem_cevabi"],
                retrieved_contexts=r["contexts"],
                reference=r["dogru_cevap"],
            )
        )

    dataset = EvaluationDataset(samples=eval_samples)

    metrics = [
        Faithfulness(llm=ragas_llm),
        ResponseRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
        LLMContextPrecisionWithoutReference(llm=ragas_llm),
        LLMContextRecall(llm=ragas_llm),
    ]

    logger.info("RAGAS evaluate basliyor (%d ornek, seri mod)...", len(eval_samples))
    eval_result = evaluate(
        dataset=dataset,
        metrics=metrics,
        batch_size=1,          # Tek tek işle — Ollama paralel isteklerde boğuluyor
        raise_exceptions=False, # Timeout olan job'lar NaN olsun, crash olmasın
    )
    eval_df = eval_result.to_pandas()

    # Sonuçları birleştir
    detail_df = pd.DataFrame([
        {
            "Soru": r["soru"],
            "Beklenen Cevap": r["dogru_cevap"],
            "Sistem Cevabi": r["sistem_cevabi"],
            "Context Bulundu": r["has_context"],
            "Sure (sn)": r["sure_sn"],
            "Kaynak": r["kaynak"],
            "Sistem Kaynaklari": ", ".join(
                f"{s.get('source_file', '')} s.{s.get('page_number', '')}"
                for s in r["sources"]
            ) if r["sources"] else "-",
        }
        for r in results
    ])

    # RAGAS skorlarını ekle
    for col in eval_df.columns:
        if col not in ("user_input", "response", "retrieved_contexts", "reference"):
            detail_df[col] = eval_df[col].values

    # Özet satırı
    summary_data = {"Soru": "ORTALAMA"}
    for col in detail_df.columns:
        if detail_df[col].dtype in ("float64", "float32"):
            summary_data[col] = round(detail_df[col].mean(), 4)
    summary_df = pd.DataFrame([summary_data])

    # Excel'e yaz
    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="Detay", index=False)
        summary_df.to_excel(writer, sheet_name="Ozet", index=False)

    logger.info("Sonuclar kaydedildi: %s", OUTPUT_PATH)

    # Özeti ekrana bas
    print("\n" + "=" * 60)
    print("RAGAS DEGERLENDIRME OZETI")
    print("=" * 60)
    for col in summary_data:
        if col != "Soru":
            print(f"  {col}: {summary_data[col]}")
    print("=" * 60)


def run() -> None:
    """İki aşamalı değerlendirme: RAG → bellek temizle → RAGAS."""
    results = phase1_rag_responses()
    phase2_ragas_evaluation(results)


if __name__ == "__main__":
    run()
