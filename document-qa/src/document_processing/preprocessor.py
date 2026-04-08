"""Metin ön işleme modülü.

Başlık tespiti ve context bleeding çözümü sağlar.
Başlıkların etrafına paragraf sınırı (\n\n) enjekte ederek
RecursiveCharacterTextSplitter'ın doğru yerlerden kesmesini sağlar.
"""

import re


def _satir_baslik_mi(satir: str) -> bool:
    """Bir satırın başlık olup olmadığını tespit eder.

    Kriterler:
    - 100 karakterden kısa
    - Nokta ile bitmiyor
    - En az 2 kelime içeriyor
    - Büyük harf veya title case
    - Harf oranı %40'ın üzerinde

    Args:
        satir: Kontrol edilecek metin satırı.

    Returns:
        True ise satır bir başlık.
    """
    satir = satir.strip()
    if not satir:
        return False
    if len(satir) > 100:
        return False
    if satir.endswith("."):
        return False
    kelimeler = satir.split()
    if len(kelimeler) < 2:
        return False
    if not (satir.isupper() or satir.istitle()):
        return False
    harf_sayisi = sum(1 for c in satir if c.isalpha())
    toplam_sayisi = len(satir)
    if toplam_sayisi == 0:
        return False
    if harf_sayisi / toplam_sayisi < 0.4:
        return False
    return True


def metin_on_isleme(text: str) -> str:
    """Metni ön işlemden geçirir: başlık sınırı enjeksiyonu + temizlik.

    Başlıkların etrafına \\n\\n ekleyerek chunk sınırlarının
    doğru bölüm geçişlerinde oluşmasını sağlar.

    Args:
        text: Ham metin.

    Returns:
        Ön işlenmiş metin.
    """
    satirlar = text.split("\n")
    islenmis: list[str] = []

    for satir in satirlar:
        if _satir_baslik_mi(satir):
            islenmis.append(f"\n\n{satir.strip()}\n\n")
        else:
            islenmis.append(satir)

    sonuc = "\n".join(islenmis)

    # Fazla boş satırları temizle (3+ ardışık newline → 2)
    sonuc = re.sub(r"\n{3,}", "\n\n", sonuc)

    return sonuc.strip()
