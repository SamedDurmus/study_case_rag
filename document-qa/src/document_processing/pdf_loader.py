"""PDF dosyalarından metin çıkarma modülü.

PyMuPDF (fitz) kullanarak PDF sayfalarından metin ve metadata çıkarır.
Scanned PDF tespiti için sayfa başına metin uzunluğu kontrolü yapar.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

SCANNED_PAGE_THRESHOLD = 50  # Karakter sayısı altında "scanned" kabul edilir


@dataclass
class PageContent:
    """Tek bir sayfadan çıkarılan içerik."""

    text: str
    page_number: int
    source_file: str
    extraction_method: str  # "text" veya "ocr"
    is_scanned: bool = False


@dataclass
class PDFResult:
    """PDF'den çıkarılan tüm içerik."""

    pages: list[PageContent] = field(default_factory=list)
    total_pages: int = 0
    source_file: str = ""


def extract_text_from_pdf(file_path: str | Path) -> PDFResult:
    """PDF dosyasından sayfa sayfa metin çıkarır.

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
        doc = fitz.open(str(file_path))
    except Exception as e:
        raise RuntimeError(f"PDF acilamadi: {file_path} - {e}") from e

    result = PDFResult(
        total_pages=len(doc),
        source_file=file_path.name,
    )

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        is_scanned = len(text) < SCANNED_PAGE_THRESHOLD

        page_content = PageContent(
            text=text,
            page_number=page_num + 1,
            source_file=file_path.name,
            extraction_method="text" if not is_scanned else "pending_ocr",
            is_scanned=is_scanned,
        )
        result.pages.append(page_content)

    doc.close()

    scanned_count = sum(1 for p in result.pages if p.is_scanned)
    logger.info(
        "PDF yuklendi: %s (%d sayfa, %d scanned)",
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
    doc = fitz.open(str(file_path))
    page = doc[page_number - 1]
    pixmap = page.get_pixmap(dpi=300)
    image_bytes = pixmap.tobytes("png")
    doc.close()
    return image_bytes
