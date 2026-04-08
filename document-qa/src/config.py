"""Merkezi konfigürasyon modülü.

Tüm parametreler .env dosyasından okunur. Varsayılan değerler
RTX 3070 Ti 16GB VRAM ortamı için optimize edilmiştir.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# Embedding & Reranker
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# Qdrant
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "documents")

# Chunking
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "80"))

# Retrieval
RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "20"))
RERANK_TOP_N: int = int(os.getenv("RERANK_TOP_N", "4"))
RERANK_SCORE_THRESHOLD: float = float(os.getenv("RERANK_SCORE_THRESHOLD", "0.0"))
RRF_K: int = int(os.getenv("RRF_K", "60"))

# OCR
OCR_LANGUAGES: list[str] = os.getenv("OCR_LANGUAGES", "tr,en").split(",")
