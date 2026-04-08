"""LLM bağlantı modülü.

Ollama API üzerinden LLM çağrısı ve streaming desteği sağlar.
"""

import logging
from collections.abc import Generator

from openai import OpenAI

from src.config import LLM_MAX_TOKENS, LLM_TEMPERATURE, OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class LLMClient:
    """Ollama LLM istemcisi.

    OpenAI uyumlu API üzerinden Ollama'ya bağlanır.
    Streaming ve non-streaming cevap üretimi destekler.
    """

    def __init__(self) -> None:
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        """OpenAI client'ı lazy olarak oluşturur."""
        if self._client is None:
            self._client = OpenAI(
                api_key="ollama",
                base_url=f"{OLLAMA_BASE_URL}/v1",
            )
            logger.info("Ollama baglantisi kuruldu: %s", OLLAMA_BASE_URL)
        return self._client

    def generate(self, prompt: str) -> str:
        """Non-streaming cevap üretir.

        Args:
            prompt: Tam prompt metni (system prompt + context + soru).

        Returns:
            LLM cevabı.
        """
        client = self._get_client()
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            stream=False,
        )
        answer = response.choices[0].message.content or ""
        logger.info("LLM cevap uretti: %d karakter", len(answer))
        return answer

    def generate_stream(self, prompt: str) -> Generator[str, None, None]:
        """Streaming cevap üretir (token token).

        Args:
            prompt: Tam prompt metni.

        Yields:
            Her bir token (str).
        """
        client = self._get_client()
        stream = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def check_connection(self) -> bool:
        """Ollama bağlantısını kontrol eder.

        Returns:
            True ise bağlantı başarılı.
        """
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception as e:
            logger.error("Ollama baglanti hatasi: %s", e)
            return False
