"""Metin parçalama (chunking) modülü.

LangChain RecursiveCharacterTextSplitter kullanarak belge metinlerini
anlamlı parçalara böler. Başlık sınırları preprocessor tarafından
enjekte edilen \\n\\n ile korunur.
"""

import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHUNK_OVERLAP, CHUNK_SIZE
from src.document_processing.smart_loader import DocumentChunk

logger = logging.getLogger(__name__)


def create_splitter() -> RecursiveCharacterTextSplitter:
    """Konfigürasyona göre text splitter oluşturur.

    Returns:
        Yapılandırılmış RecursiveCharacterTextSplitter.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )


def chunk_documents(document_chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    """Belge parçalarını chunk'lara böler.

    Her DocumentChunk'ın text'ini splitter ile böler,
    metadata'yı koruyarak yeni chunk'lar oluşturur.

    Args:
        document_chunks: SmartLoader'dan gelen belge parçaları.

    Returns:
        Bölünmüş chunk listesi (her biri metadata ile).
    """
    splitter = create_splitter()
    result: list[DocumentChunk] = []

    for doc_chunk in document_chunks:
        texts = splitter.split_text(doc_chunk.text)
        for i, text in enumerate(texts):
            new_chunk = DocumentChunk(
                text=text,
                metadata={
                    **doc_chunk.metadata,
                    "chunk_index": i,
                    "total_chunks_in_page": len(texts),
                },
            )
            result.append(new_chunk)

    logger.info(
        "Chunking tamamlandi: %d belge parcasi -> %d chunk",
        len(document_chunks),
        len(result),
    )
    return result
