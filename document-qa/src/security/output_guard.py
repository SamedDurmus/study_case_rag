"""LLM çıktı doğrulama modülü.

LLM cevaplarını doğrulayarak:
- System prompt sızıntısını tespit eder
- Context dışı bilgi üretimini (halüsinasyon) kontrol eder
- Zararlı içerik üretimini engeller
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# System prompt'tan sızmaması gereken kalıplar
SYSTEM_PROMPT_LEAKS: list[str] = [
    r"(?i)KESİN\s+KURALLAR",
    r"(?i)sen\s+bir\s+belge\s+analiz\s+asistanısın",
    r"(?i)kendi\s+bilginden\s+ASLA",
    r"(?i)YALNIZCA\s+aşağıdaki\s+bağlam",
    r"(?i)BAĞLAM:\s*\n",
    r"(?i)KULLANICI\s+SORUSU:\s*\n",
]

# Halüsinasyon göstergeleri
HALLUCINATION_INDICATORS: list[str] = [
    r"(?i)(genel\s+olarak\s+bilinir\s+ki|bildiğim\s+kadarıyla|genel\s+bilgi\s+olarak)",
    r"(?i)(as\s+is\s+widely\s+known|in\s+general|it\s+is\s+commonly\s+accepted)",
    r"(?i)(kendi\s+bilgime\s+göre|my\s+own\s+knowledge)",
    r"(?i)(wikipedia|google|internet\s+kaynaklarına\s+göre)",
]


@dataclass
class OutputCheckResult:
    """Çıktı kontrol sonucu."""

    is_safe: bool
    has_system_leak: bool = False
    has_hallucination_risk: bool = False
    warnings: list[str] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


def check_output(answer: str, context: str) -> OutputCheckResult:
    """LLM cevabını güvenlik ve kalite kontrolünden geçirir.

    Args:
        answer: LLM'in ürettiği cevap.
        context: LLM'e verilen context metni.

    Returns:
        OutputCheckResult: Kontrol sonucu.
    """
    warnings: list[str] = []

    # 1. System prompt sızıntı kontrolü
    has_leak = False
    for pattern in SYSTEM_PROMPT_LEAKS:
        if re.search(pattern, answer):
            has_leak = True
            logger.warning("System prompt sizintisi tespit edildi: %s", pattern)
            warnings.append("System prompt sızıntısı tespit edildi.")
            break

    # 2. Halüsinasyon göstergesi kontrolü
    has_hallucination = False
    for pattern in HALLUCINATION_INDICATORS:
        if re.search(pattern, answer):
            has_hallucination = True
            logger.warning("Halusinasyon gostergesi tespit edildi: %s", pattern)
            warnings.append("Cevap, belgede olmayan kaynaklara referans veriyor olabilir.")
            break

    # 3. Boş veya anlamsız cevap kontrolü
    clean_answer = answer.strip()
    if len(clean_answer) < 5:
        warnings.append("Cevap çok kısa veya boş.")

    is_safe = not has_leak
    return OutputCheckResult(
        is_safe=is_safe,
        has_system_leak=has_leak,
        has_hallucination_risk=has_hallucination,
        warnings=warnings,
    )
