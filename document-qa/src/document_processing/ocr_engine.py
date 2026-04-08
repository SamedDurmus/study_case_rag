"""OCR motoru modülü.

EasyOCR kullanarak resim dosyalarından veya image byte'larından
Türkçe + İngilizce metin çıkarır. Lazy loading ile model
sadece ilk kullanımda yüklenir.
"""

import io
import logging
from pathlib import Path

import easyocr
import numpy as np
from PIL import Image

from src.config import OCR_LANGUAGES

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.3  # Bu değerin altındaki OCR sonuçları filtrelenir


class OCREngine:
    """EasyOCR tabanlı metin çıkarma motoru.

    Lazy loading: Model ilk extract_text çağrısında yüklenir,
    sonraki çağrılarda tekrar yüklenmez.
    """

    def __init__(self, languages: list[str] | None = None) -> None:
        """OCREngine başlatır.

        Args:
            languages: OCR dilleri listesi. None ise config'den okunur.
        """
        self._reader: easyocr.Reader | None = None
        self._languages = languages or OCR_LANGUAGES

    def _get_reader(self) -> easyocr.Reader:
        """EasyOCR reader'ı lazy olarak yükler."""
        if self._reader is None:
            logger.info("EasyOCR modeli yukleniyor: %s", self._languages)
            self._reader = easyocr.Reader(self._languages, gpu=True)
            logger.info("EasyOCR modeli yuklendi.")
        return self._reader

    def extract_text_from_file(self, image_path: str | Path) -> str:
        """Resim dosyasından metin çıkarır.

        Args:
            image_path: Resim dosyasının yolu (.jpg, .jpeg, .png).

        Returns:
            Çıkarılan metin.

        Raises:
            FileNotFoundError: Dosya bulunamazsa.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Resim dosyasi bulunamadi: {image_path}")

        reader = self._get_reader()
        results = reader.readtext(str(image_path))
        text = self._results_to_text(results)

        logger.info(
            "OCR tamamlandi: %s (%d karakter)",
            image_path.name,
            len(text),
        )
        return text

    def extract_text_from_bytes(self, image_bytes: bytes) -> str:
        """Image byte'larından metin çıkarır (scanned PDF sayfaları için).

        Args:
            image_bytes: PNG/JPG formatında image byte'ları.

        Returns:
            Çıkarılan metin.
        """
        reader = self._get_reader()
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)
        results = reader.readtext(image_np)
        return self._results_to_text(results)

    def _results_to_text(self, results: list) -> str:
        """EasyOCR sonuçlarını metne çevirir, düşük güvenlikli sonuçları filtreler.

        Args:
            results: EasyOCR readtext() çıktısı.

        Returns:
            Birleştirilmiş metin.
        """
        lines = [text for _, text, conf in results if conf > MIN_CONFIDENCE]
        return "\n".join(lines)
