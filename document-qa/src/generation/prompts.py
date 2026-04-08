"""Prompt şablonları modülü.

RAG pipeline için system prompt ve context builder fonksiyonları.
"""

SYSTEM_PROMPT = """Sen bir belge analiz asistanısın.
Kullanıcının yüklediği belgeler hakkında soruları yanıtlıyorsun.

KESİN KURALLAR:
1. YALNIZCA aşağıdaki bağlamdaki bilgileri kullan
2. Kendi bilginden ASLA ekleme yapma
3. Bağlamda cevap yoksa "Bu konuda yüklenen belgelerde bilgi bulunamadı." de
4. Cevabını Türkçe veya İngilizce, kullanıcının sorusunun diline göre ver
5. Cevabın sonuna kaynak bilgisi ekle: [Kaynak: dosya_adı, Sayfa: X]

BAĞLAM:
{context}

KULLANICI SORUSU:
{question}"""


def build_context(search_results: list[dict]) -> str:
    """Arama sonuçlarından LLM'e verilecek context metni oluşturur.

    Args:
        search_results: Reranker'dan gelen sonuç listesi.
            Her biri {"text", "metadata"} içerir.

    Returns:
        Formatlanmış context metni.
    """
    if not search_results:
        return ""

    context_parts: list[str] = []
    for i, result in enumerate(search_results, start=1):
        source = result.get("metadata", {}).get("source_file", "bilinmiyor")
        page = result.get("metadata", {}).get("page_number", "?")
        text = result.get("text", "")

        context_parts.append(
            f"[Kaynak {i}: {source}, Sayfa {page}]\n{text}"
        )

    return "\n\n---\n\n".join(context_parts)


def format_prompt(context: str, question: str) -> str:
    """System prompt'u context ve soru ile doldurur.

    Args:
        context: build_context'ten gelen formatlanmış context.
        question: Kullanıcının sorusu.

    Returns:
        Tam prompt metni.
    """
    return SYSTEM_PROMPT.format(context=context, question=question)
