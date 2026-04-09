"""OCR motoru modülü.

EasyOCR kullanarak resim dosyalarından veya image byte'larından
Türkçe + İngilizce metin çıkarır. Lazy loading ile model
sadece ilk kullanımda yüklenir.

OCR öncesi image preprocessing uygulanır:
- Grayscale dönüşüm (renk noise'u azaltır)
- Düşük çözünürlüklü resimler upscale edilir (min 3000px genişlik)
- Kontrast artırma + sharpening ile metin kenarları keskinleştirilir

OCR sonrası text reconstruction uygulanır:
- Bounding box koordinatlarına göre metin blokları sıralanır (yukarıdan aşağı)
- Aynı satırdaki bloklar birleştirilir (satır yüksekliğine göre proximity)
- Kısa noise bloklar filtrelenir (footer, dekoratif metin)
"""

import io
import logging
from pathlib import Path

import easyocr
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from src.config import OCR_LANGUAGES

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.3  # Bu değerin altındaki OCR sonuçları filtrelenir
MIN_WIDTH_FOR_OCR = 3000  # Bu genişliğin altındaki resimler upscale edilir
MIN_LINE_LENGTH = 3  # Bu uzunluğun altındaki satırlar noise kabul edilir


class OCREngine:
    """EasyOCR tabanlı metin çıkarma motoru.

    Lazy loading: Model ilk extract_text çağrısında yüklenir,
    sonraki çağrılarda tekrar yüklenmez.
    """

    def __init__(self, languages: list[str] | None = None) -> None:
        self._reader: easyocr.Reader | None = None
        self._languages = languages or OCR_LANGUAGES

    def _get_reader(self) -> easyocr.Reader:
        """EasyOCR reader'ı lazy olarak yükler."""
        if self._reader is None:
            logger.info("EasyOCR modeli yukleniyor: %s", self._languages)
            self._reader = easyocr.Reader(self._languages, gpu=True)
            logger.info("EasyOCR modeli yuklendi.")
        return self._reader

    def _preprocess_image(self, image: Image.Image) -> np.ndarray:
        """OCR öncesi resmi iyileştirir.

        1. Grayscale (renk noise'u azalt)
        2. Upscale (küçük resimlerde OCR zayıf)
        3. Kontrast artır (metin/arka plan ayrımı)
        4. Sharpen (karakter kenarları keskinleşir)

        Args:
            image: PIL Image nesnesi.

        Returns:
            İşlenmiş numpy array.
        """
        # 1. Grayscale
        image = image.convert("L")

        # 2. Upscale
        width, height = image.size
        if width < MIN_WIDTH_FOR_OCR:
            scale = MIN_WIDTH_FOR_OCR / width
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.LANCZOS)
            logger.debug(
                "Resim upscale edildi: %dx%d -> %dx%d (%.1fx)",
                width, height, new_size[0], new_size[1], scale,
            )

        # 3. Kontrast artır
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        # 4. Sharpen (iki geçiş)
        image = image.filter(ImageFilter.SHARPEN)
        image = image.filter(ImageFilter.SHARPEN)

        return np.array(image)

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

        image = Image.open(image_path)
        processed = self._preprocess_image(image)

        reader = self._get_reader()
        results = reader.readtext(processed)
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
        image = Image.open(io.BytesIO(image_bytes))
        processed = self._preprocess_image(image)

        reader = self._get_reader()
        results = reader.readtext(processed)
        return self._results_to_text(results)

    def _results_to_text(self, results: list) -> str:
        """EasyOCR sonuçlarını pozisyon bazlı sıralayıp tutarlı metne çevirir.

        1. Düşük güvenlikli sonuçları filtrele
        2. Bounding box'a göre yukarıdan aşağı sırala
        3. Aynı satırdaki blokları birleştir (y-koordinat yakınlığı)
        4. Kısa noise satırları filtrele

        Args:
            results: EasyOCR readtext() çıktısı.
                Her eleman: ([[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence)

        Returns:
            Birleştirilmiş ve sıralanmış metin.
        """
        # 1. Confidence filtresi
        filtered = [
            (bbox, text, conf)
            for bbox, text, conf in results
            if conf > MIN_CONFIDENCE
        ]

        if not filtered:
            return ""

        # 2. Pozisyona göre sırala (y önce, x sonra)
        filtered.sort(key=lambda r: (self._bbox_y(r[0]), self._bbox_x(r[0])))

        # 3. Aynı satırdaki blokları birleştir
        lines: list[str] = []
        current_parts: list[str] = []
        current_y = self._bbox_y(filtered[0][0])
        current_height = self._bbox_height(filtered[0][0])

        for bbox, text, _conf in filtered:
            y = self._bbox_y(bbox)
            h = self._bbox_height(bbox)
            threshold = max(current_height, h) * 0.5

            if abs(y - current_y) > threshold:
                # Yeni satır — önceki satırı kaydet
                if current_parts:
                    lines.append(" ".join(current_parts))
                current_parts = [text]
                current_y = y
                current_height = h
            else:
                # Aynı satır — ekle
                current_parts.append(text)

        # Son satırı kaydet
        if current_parts:
            lines.append(" ".join(current_parts))

        # 4. Noise filtresi — çok kısa satırları kaldır
        lines = [line for line in lines if len(line.strip()) >= MIN_LINE_LENGTH]

        return "\n".join(lines)

    @staticmethod
    def _bbox_y(bbox: list) -> float:
        """Bounding box'ın orta Y koordinatı."""
        return (bbox[0][1] + bbox[2][1]) / 2

    @staticmethod
    def _bbox_x(bbox: list) -> float:
        """Bounding box'ın sol X koordinatı."""
        return bbox[0][0]

    @staticmethod
    def _bbox_height(bbox: list) -> float:
        """Bounding box'ın yüksekliği."""
        return abs(bbox[2][1] - bbox[0][1])
