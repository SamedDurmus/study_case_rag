"""Akıllı belge yükleyici modülü.

Dosya uzantısına göre otomatik yönlendirme yapar:
- PDF → pymupdf4llm ile Markdown formatında metin çıkarma, scanned sayfalar için EasyOCR fallback
- JPG/PNG → EasyOCR ile metin çıkarma
- Diğer → Desteklenmeyen format hatası
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.document_processing.ocr_engine import OCREngine
from src.document_processing.pdf_loader import (
    PDFResult,
    extract_page_as_image,
    extract_text_from_pdf,
)
from src.document_processing.preprocessor import metin_on_isleme

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS


@dataclass
class DocumentChunk:
    """İşlenmiş belge parçası, chunking aşamasına hazır."""

    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class LoadResult:
    """Belge yükleme sonucu."""

    chunks: list[DocumentChunk] = field(default_factory=list)
    source_file: str = ""
    total_pages: int = 0
    extraction_method: str = ""


class SmartLoader:
    """Dosya tipine göre otomatik metin çıkarma ve ön işleme.

    OCR engine lazy olarak paylaşılır — birden fazla dosya
    yüklendiğinde model tekrar yüklenmez.
    """

    def __init__(self) -> None:
        self._ocr_engine: OCREngine | None = None

    def _get_ocr_engine(self) -> OCREngine:
        """OCR engine'i lazy olarak yükler."""
        if self._ocr_engine is None:
            self._ocr_engine = OCREngine()
        return self._ocr_engine

    def load(
        self, file_path: str | Path, original_filename: str | None = None
    ) -> LoadResult:
        """Dosyayı yükler, metin çıkarır ve ön işler.

        Args:
            file_path: Belge dosyasının yolu.
            original_filename: Orijinal dosya adı (temp dosya kullanılıyorsa).

        Returns:
            LoadResult: İşlenmiş metin parçaları ve metadata.

        Raises:
            ValueError: Desteklenmeyen dosya formatı.
            FileNotFoundError: Dosya bulunamazsa.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Dosya bulunamadi: {file_path}")

        display_name = original_filename or file_path.name
        extension = file_path.suffix.lower()

        if extension in SUPPORTED_PDF_EXTENSIONS:
            return self._load_pdf(file_path, display_name)
        elif extension in SUPPORTED_IMAGE_EXTENSIONS:
            return self._load_image(file_path, display_name)
        else:
            raise ValueError(
                f"Desteklenmeyen dosya formati: {extension}. "
                f"Desteklenen formatlar: {SUPPORTED_EXTENSIONS}"
            )

    def _load_pdf(self, file_path: Path, display_name: str) -> LoadResult:
        """PDF dosyasını yükler, scanned sayfalar için OCR uygular.

        Args:
            file_path: PDF dosyasının yolu.
            display_name: Gösterilecek dosya adı.

        Returns:
            LoadResult: İşlenmiş sayfa içerikleri.
        """
        pdf_result: PDFResult = extract_text_from_pdf(file_path)
        result = LoadResult(
            source_file=display_name,
            total_pages=pdf_result.total_pages,
        )

        has_ocr = False
        for page in pdf_result.pages:
            text = page.text
            method = page.extraction_method

            # Scanned sayfa: OCR uygula
            if page.is_scanned:
                logger.info(
                    "Scanned sayfa tespit edildi: %s sayfa %d, OCR uygulanıyor",
                    display_name,
                    page.page_number,
                )
                image_bytes = extract_page_as_image(file_path, page.page_number)
                text = self._get_ocr_engine().extract_text_from_bytes(image_bytes)
                method = "ocr"
                has_ocr = True

            if not text.strip():
                continue

            processed_text = metin_on_isleme(text)

            chunk = DocumentChunk(
                text=processed_text,
                metadata={
                    "source_file": display_name,
                    "page_number": page.page_number,
                    "extraction_method": method,
                    "total_pages": pdf_result.total_pages,
                },
            )
            result.chunks.append(chunk)

        result.extraction_method = "text+ocr" if has_ocr else "text"
        logger.info(
            "PDF islendi: %s (%d sayfa, %d metin parcasi, yontem: %s)",
            display_name,
            result.total_pages,
            len(result.chunks),
            result.extraction_method,
        )
        return result

    def _load_image(self, file_path: Path, display_name: str) -> LoadResult:
        """Resim dosyasından OCR ile metin çıkarır.

        Args:
            file_path: Resim dosyasının yolu.
            display_name: Gösterilecek dosya adı.

        Returns:
            LoadResult: Çıkarılan metin.
        """
        text = self._get_ocr_engine().extract_text_from_file(file_path)

        if not text.strip():
            logger.warning("Resimden metin cikarilAmadi: %s", display_name)
            return LoadResult(
                source_file=display_name,
                total_pages=1,
                extraction_method="ocr",
            )

        processed_text = metin_on_isleme(text)

        result = LoadResult(
            source_file=display_name,
            total_pages=1,
            extraction_method="ocr",
            chunks=[
                DocumentChunk(
                    text=processed_text,
                    metadata={
                        "source_file": display_name,
                        "page_number": 1,
                        "extraction_method": "ocr",
                        "total_pages": 1,
                    },
                )
            ],
        )

        logger.info(
            "Resim islendi: %s (%d karakter)",
            display_name,
            len(processed_text),
        )
        return result
