"""Belge içeriği güvenlik modülü.

Yüklenen belgelerden gelebilecek indirect prompt injection'ları tespit eder.
Belgeler içinde gizlenmiş LLM talimatlarını yakalar.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Belge içinde olmaması gereken talimat kalıpları
INDIRECT_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # LLM'e doğrudan talimat
    (r"(?i)(ignore\s+(all\s+)?previous|disregard\s+(above|prior))\s+(context|instructions?|rules?)", "instruction_override"),
    # Rol değiştirme gizleme
    (r"(?i)(you\s+are\s+now|act\s+as\s+if|pretend\s+to\s+be|from\s+now\s+on\s+you)", "hidden_role_change"),
    # System prompt manipülasyonu
    (r"(?i)(new\s+system\s+prompt|override\s+instructions?|replace\s+your\s+rules?)", "system_override"),
    # Delimiter injection
    (r"(<\/?system>|<\/?user>|<\/?assistant>|\[INST\]|\[\/INST\])", "delimiter_injection"),
    # Gizli talimat formatları (görünmez unicode, zero-width chars)
    (r"[\u200b\u200c\u200d\u2060\ufeff]{3,}", "hidden_unicode"),
    # Base64 encoded komutlar (uzun base64 blokları şüpheli)
    (r"(?i)(execute|eval|run)\s*\(\s*base64", "encoded_command"),
]


def check_document_content(text: str, source_file: str = "") -> list[str]:
    """Belge metnini indirect injection açısından kontrol eder.

    Args:
        text: Belgeden çıkarılan metin.
        source_file: Kaynak dosya adı (loglama için).

    Returns:
        Tespit edilen tehdit listesi (boş liste = güvenli).
    """
    threats: list[str] = []

    for pattern, pattern_name in INDIRECT_INJECTION_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            logger.warning(
                "Indirect injection tespit edildi: dosya=%s, pattern=%s, eslesme=%d",
                source_file,
                pattern_name,
                len(matches),
            )
            threats.append(pattern_name)

    return threats


def sanitize_context(text: str) -> str:
    """Context metninden potansiyel injection kalıplarını temizler.

    Tehlikeli kalıpları kaldırmaz (bilgi kaybı olur),
    bunun yerine LLM'in talimat olarak yorumlamasını
    engellemek için delimiter'ları escape eder.

    Args:
        text: Ham context metni.

    Returns:
        Temizlenmiş metin.
    """
    # Delimiter'ları düz metne çevir
    text = re.sub(r"<(/?)system>", r"[\1system]", text)
    text = re.sub(r"<(/?)user>", r"[\1user]", text)
    text = re.sub(r"<(/?)assistant>", r"[\1assistant]", text)
    text = re.sub(r"\[INST\]", "[inst]", text)
    text = re.sub(r"\[/INST\]", "[/inst]", text)

    # Zero-width karakterleri temizle
    text = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", text)

    return text
