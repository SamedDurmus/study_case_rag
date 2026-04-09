"""PDF dosyalarından metin çıkarma modülü.

pymupdf4llm kullanarak PDF sayfalarından Markdown formatında metin çıkarır.
Markdown çıktısı başlık hiyerarşisi ve tablo yapısını korur — LLM için ideal.
Scanned PDF tespiti için sayfa başına metin uzunluğu kontrolü yapar.

Not: pymupdf4llm dahili OCR için Tesseract kullanır, ancak biz
EasyOCR tercih ettiğimiz için use_ocr=False ile çalıştırıyoruz.
Scanned sayfa tespiti yapılır, OCR smart_loader tarafından EasyOCR ile uygulanır.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf  # PyMuPDF — sayfa image'a dönüştürme için (OCR fallback)
import pymupdf4llm  # LLM-optimized Markdown çıktı

logger = logging.getLogger(__name__)

SCANNED_PAGE_THRESHOLD = 50  # Karakter sayısı altında "scanned" kabul edilir


@dataclass
class PageContent:
    """Tek bir sayfadan çıkarılan içerik."""

    text: str
    page_number: int
    source_file: str
    extraction_method: str  # "text" veya "pending_ocr"
    is_scanned: bool = False


@dataclass
class PDFResult:
    """PDF'den çıkarılan tüm içerik."""

    pages: list[PageContent] = field(default_factory=list)
    total_pages: int = 0
    source_file: str = ""


def _clean_text_length(text: str) -> int:
    """Markdown formatting karakterleri hariç metin uzunluğunu döndürür.

    Scanned sayfa tespitinde Markdown işaretleri (#, *, -, |, ---)
    yanlış pozitif yaratmaması için temizlenmiş uzunluk hesaplanır.
    """
    clean = text.replace("#", "").replace("*", "").replace("-", "").replace("|", "")
    return len(clean.strip())


def extract_text_from_pdf(file_path: str | Path) -> PDFResult:
    """PDF dosyasından sayfa sayfa Markdown formatında metin çıkarır.

    pymupdf4llm ile Markdown çıktı alınır — başlık hiyerarşisi ve
    tablo yapısı korunur. Scanned sayfalar is_scanned=True olarak
    işaretlenir, OCR smart_loader tarafından EasyOCR ile uygulanır.

    Args:
        file_path: PDF dosyasının yolu.

    Returns:
        PDFResult: Sayfa içerikleri ve metadata.

    Raises:
        FileNotFoundError: Dosya bulunamazsa.
        RuntimeError: PDF açılamazsa.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF dosyasi bulunamadi: {file_path}")

    try:
        pages = pymupdf4llm.to_markdown(
            str(file_path),
            page_chunks=True,
            use_ocr=False,  # OCR'u biz EasyOCR ile yönetiyoruz
        )
    except Exception as e:
        raise RuntimeError(f"PDF acilamadi: {file_path} - {e}") from e

    result = PDFResult(
        total_pages=len(pages),
        source_file=file_path.name,
    )

    for i, page_data in enumerate(pages):
        text = page_data.get("text", "")
        meta = page_data.get("metadata", {})
        page_num = meta.get("page", i + 1)
        is_scanned = _clean_text_length(text) < SCANNED_PAGE_THRESHOLD

        page_content = PageContent(
            text=text,
            page_number=page_num,
            source_file=file_path.name,
            extraction_method="text" if not is_scanned else "pending_ocr",
            is_scanned=is_scanned,
        )
        result.pages.append(page_content)

    scanned_count = sum(1 for p in result.pages if p.is_scanned)
    logger.info(
        "PDF yuklendi: %s (%d sayfa, %d scanned, format: markdown)",
        file_path.name,
        result.total_pages,
        scanned_count,
    )

    return result


def extract_page_as_image(file_path: str | Path, page_number: int) -> bytes:
    """PDF sayfasını PNG image olarak döndürür (OCR için).

    Args:
        file_path: PDF dosyasının yolu.
        page_number: 1-indexed sayfa numarası.

    Returns:
        PNG formatında image bytes.
    """
    doc = pymupdf.open(str(file_path))
    page = doc[page_number - 1]
    pixmap = page.get_pixmap(dpi=300)
    image_bytes = pixmap.tobytes("png")
    doc.close()
    return image_bytes
