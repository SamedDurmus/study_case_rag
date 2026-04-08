"""Kullanıcı girişi güvenlik modülü.

Prompt injection saldırılarını tespit eder.
Kural tabanlı (regex) yaklaşım — LLM çağrısı gerektirmez, deterministik.

Önemli: Tüm pattern'lerde \b (word boundary) kullanılır.
Türkçe'de "-dan", "-run" gibi ekler false positive yarattığı için
kelime sınırı olmadan kısa terimler kullanılmaz.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Prompt injection kalıpları (Türkçe + İngilizce)
# Her pattern \b word boundary ile sarılı — substring eşleşmesi önlenir
INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Rol değiştirme (EN) — "forget/ignore ... previous/prior ... instructions/rules/prompt"
    (r"(?i)\b(ignore|forget|disregard)\b.{0,20}\b(previous|above|prior|earlier|all)\b.{0,20}\b(instructions?|rules?|prompts?|context|orders?|directions?)\b", "role_override_en"),
    # Rol değiştirme (TR) — "önceki talimatları unut"
    (r"(?i)\b(önceki|yukarıdaki|mevcut|verilen)\b.{0,20}\b(talimatları?|kuralları?|promptu?|yönergeleri?)\b.{0,20}\b(unut|görmezden\s+gel|yoksay|iptal\s+et|geçersiz)", "role_override_tr"),
    # Yeni rol atama (EN)
    (r"(?i)\byou\s+are\s+(now|actually|henceforth)\s+", "new_role_en"),
    # Yeni rol atama (TR)
    (r"(?i)\b(sen\s+artık|sen\s+aslında|rolün\s+şimdi|bundan\s+sonra\s+sen)\b", "new_role_tr"),
    # System prompt sızdırma (EN) — "show/give/reveal ... system prompt/instructions"
    (r"(?i)\b(show|reveal|print|repeat|output|give|display|tell)\b.{0,20}\b(system\s+prompt|initial\s+prompt|instructions?|hidden\s+rules?|original\s+prompt)\b", "system_leak_en"),
    # System prompt sızdırma (TR) — "sistem promptunu göster"
    (r"(?i)\b(sistem\s+promptu|sistem\s+talimatı|gizli\s+kurallar|orijinal\s+prompt)\w*\s+(göster|ver|yaz|tekrarla|paylaş|söyle)", "system_leak_tr"),
    # Delimiter/escape girişimleri
    (r"(<\/?system>|<\/?user>|<\/?assistant>|\[INST\]|\[\/INST\])", "delimiter_escape"),
    # Doğrudan komut enjeksiyonu — sadece tam kelime eşleşmesi
    (r"(?i)\b(subprocess|__import__|exec\s*\(|eval\s*\(|import\s+os)\b", "code_injection"),
    # Jailbreak kalıpları (EN) — "DAN" sadece tek başına, "do anything now" tam ifade
    (r"(?i)\b(do\s+anything\s+now|developer\s+mode|jailbreak)\b", "jailbreak_en"),
    (r"(?i)(?<!\w)DAN(?!\w)", "jailbreak_dan"),
    # Jailbreak kalıpları (TR)
    (r"(?i)\b(geliştirici\s+modu|sınırsız\s+mod|kısıtlamaları?\s+(kaldır|devre\s+dışı))\b", "jailbreak_tr"),
]

# Soru minimum/maksimum uzunluk
MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 2000


@dataclass
class InputCheckResult:
    """Giriş kontrol sonucu."""

    is_safe: bool
    reason: str = ""
    matched_pattern: str = ""


def check_input(query: str) -> InputCheckResult:
    """Kullanıcı sorgusunu güvenlik kontrolünden geçirir.

    Args:
        query: Kullanıcının sorusu.

    Returns:
        InputCheckResult: Güvenlik kontrolü sonucu.
    """
    # Uzunluk kontrolü
    if len(query.strip()) < MIN_QUERY_LENGTH:
        return InputCheckResult(
            is_safe=False,
            reason="Soru çok kısa. Lütfen daha detaylı bir soru sorun.",
        )

    if len(query) > MAX_QUERY_LENGTH:
        return InputCheckResult(
            is_safe=False,
            reason=f"Soru çok uzun (maks {MAX_QUERY_LENGTH} karakter).",
        )

    # Injection pattern kontrolü
    for pattern, pattern_name in INJECTION_PATTERNS:
        if re.search(pattern, query):
            logger.warning(
                "Prompt injection tespit edildi: pattern=%s, query='%s'",
                pattern_name,
                query[:100],
            )
            return InputCheckResult(
                is_safe=False,
                reason="Bu soru güvenlik kontrolünden geçemedi. Lütfen belge içeriğiyle ilgili bir soru sorun.",
                matched_pattern=pattern_name,
            )

    return InputCheckResult(is_safe=True)
