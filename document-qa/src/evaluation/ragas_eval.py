"""RAGAS değerlendirme modülü.

Ollama üzerinden RAGAS metriklerini hesaplar.
4 temel metrik: Faithfulness, ResponseRelevancy, ContextPrecision, ContextRecall.
"""

import logging

from openai import OpenAI
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

logger = logging.getLogger(__name__)


def create_eval_dataset(
    samples: list[dict],
) -> EvaluationDataset:
    """Test verilerinden RAGAS evaluation dataset oluşturur.

    Args:
        samples: Test örnekleri listesi. Her biri:
            - "question": str
            - "answer": str (sistem cevabı)
            - "contexts": list[str] (retrieve edilen context'ler)
            - "ground_truth": str (beklenen cevap, opsiyonel)

    Returns:
        RAGAS EvaluationDataset.
    """
    eval_samples = []
    for sample in samples:
        eval_samples.append(
            SingleTurnSample(
                user_input=sample["question"],
                response=sample["answer"],
                retrieved_contexts=sample["contexts"],
                reference=sample.get("ground_truth", ""),
            )
        )
    return EvaluationDataset(samples=eval_samples)


def run_evaluation(samples: list[dict]) -> dict:
    """RAGAS değerlendirmesi çalıştırır.

    Args:
        samples: Test örnekleri (create_eval_dataset formatında).

    Returns:
        Metrik sonuçları dict'i.
    """
    # Ollama LLM wrapper
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.0,
    )
    ragas_llm = LangchainLLMWrapper(llm)

    # Embedding wrapper
    embeddings = HuggingFaceBgeEmbeddings(model_name=EMBEDDING_MODEL)
    ragas_embeddings = LangchainEmbeddingsWrapper(embeddings)

    # Metrikler
    metrics = [
        Faithfulness(llm=ragas_llm),
        ResponseRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
        LLMContextPrecisionWithoutReference(llm=ragas_llm),
        LLMContextRecall(llm=ragas_llm),
    ]

    dataset = create_eval_dataset(samples)

    logger.info("RAGAS degerlendirmesi basliyor: %d ornek", len(samples))
    results = evaluate(
        dataset=dataset,
        metrics=metrics,
    )
    logger.info("RAGAS degerlendirmesi tamamlandi.")

    return results.to_pandas().to_dict()
