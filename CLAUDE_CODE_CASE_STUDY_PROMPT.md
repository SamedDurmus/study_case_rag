# CASE STUDY: Belge Analiz ve Soru-Cevap Sistemi

## PROJE TANIMI

Kullanıcıların PDF ve resim (JPG/PNG) formatında belgeler yükleyip, bu belgeler üzerinden doğal dilde Türkçe/İngilizce soru sorabileceği yapay zeka destekli bir RAG sistemi geliştiriyorum. Savunma sanayi şirketinde LLM Mühendisi pozisyonu için teknik değerlendirme case study'si.

## KRİTİK KURALLAR

1. **MVP — işlevsel, temiz, anlaşılır.** Over-engineering YAPMA. Çalışan, iyi dökümante edilmiş, kolay çalıştırılabilir bir sistem.
2. **Her mimari karar GEREKÇELİ olmalı.** "Neden bu teknoloji?" her yerde açıklanmalı. DEVLOG.md'ye yansımalı.
3. **Karşı taraf kolay çalıştırabilmeli.** Qdrant + Streamlit Docker'da. Ollama host'ta (GPU erişimi için). Toplam 3 komut: `ollama pull model`, `docker compose up`, tarayıcı aç.
4. **Model değiştirilebilir olmalı.** .env'de model adı değiştirmek yeterli olmalı. README'de GPU'ya göre model önerileri tablosu olmalı.
5. **Türkçe + İngilizce** her yerde desteklenmeli.
6. **Agent/tool calling KULLANMA.** Deterministik RAG pipeline yeterli. DEVLOG'da "Agent değerlendirdim ama MVP için deterministik pipeline daha güvenilir" yaz.
7. **LangChain kullanılabilir** ama sadece gerektiği yerde — LCEL zincirleme, document loader, text splitter. Gereksiz soyutlama ekleme.

## DONANIM KISITLARI

- GPU: NVIDIA RTX 3070 Ti 16GB VRAM
- RAM: 16GB
- Varsayılan model: Qwen 2.5 7B Instruct Q4_K_M (~4.5GB VRAM)
- BGE-M3 embedding: ~2GB VRAM
- BGE-Reranker: ~1.5GB VRAM
- Toplam: ~8GB VRAM, 16GB içinde rahat

## PROJE YAPISI

```
document-qa/
├── README.md                   # Kurulum + çalıştırma + model tablosu + mimari açıklama
├── DEVLOG.md                   # Geliştirme günlüğü (her karar gerekçeli)
├── TESTING.md                  # Test senaryoları + gerçek çıktılar
├── docker-compose.yml          # Qdrant + Streamlit app
├── Dockerfile                  # Python uygulaması container'ı
├── .env.example                # Örnek config (gizli bilgi olmadan)
├── .env                        # Gerçek config (gitignore'da)
├── .gitignore
├── requirements.txt
│
├── app.py                      # Streamlit ana uygulama
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Merkezi config (.env'den okur)
│   │
│   ├── document_processing/
│   │   ├── __init__.py
│   │   ├── pdf_loader.py       # PDF metin çıkarma (PyMuPDF)
│   │   ├── ocr_engine.py       # Resim → metin (EasyOCR, TR+EN)
│   │   ├── smart_loader.py     # Akıllı yönlendirici: PDF mi? Resim mi? Scanned PDF mi?
│   │   └── preprocessor.py     # Başlık tespiti + context bleeding çözümü
│   │
│   ├── indexing/
│   │   ├── __init__.py
│   │   ├── chunker.py          # RecursiveCharacterTextSplitter
│   │   └── embedder.py         # BGE-M3 embedding + Qdrant yazma
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── hybrid_search.py    # Dense + Sparse paralel arama
│   │   ├── rrf.py              # RRF birleştirme (ayrı, test edilebilir)
│   │   └── reranker.py         # BGE-Reranker cross-encoder
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── llm.py              # Ollama bağlantısı + streaming
│   │   ├── prompts.py          # System prompt + context builder
│   │   └── chain.py            # RAG chain (retrieval → context → LLM → cevap)
│   │
│   └── evaluation/
│       ├── __init__.py
│       └── ragas_eval.py       # RAGAS metrikleri (Ollama üzerinden)
│
├── data/
│   └── test_documents/         # Örnek test dokümanları (1-2 PDF + 1-2 resim)
│
└── tests/
    ├── __init__.py
    └── test_core.py            # Temel unit testler
```

## TEKNOLOJİ SEÇİMLERİ VE GEREKÇELERİ

### LLM: Ollama + Qwen 2.5 7B Instruct (Q4_K_M)
- **Neden Qwen 2.5:** Türkçe'de LLaMA 7B'den güçlü (çok dilli eğitim verisi). Instruction following güçlü. RAGAS iç promptlarını güvenilir çözüyor.
- **Neden 7B:** 3B RAGAS çözemiyordu (önceki projede test ettim). 7B minimum güvenilir boyut. Q4 ile 4.5GB VRAM.
- **Neden Ollama:** Tek komutla model indirip API sunar. Air-gapped uyumlu. Model değiştirmek tek satır (.env).
- **Model değiştirilebilirlik:** .env'de OLLAMA_MODEL değiştirmek yeterli. Kod hiç değişmez.

### Embedding: BGE-M3 (BAAI/bge-m3, use_fp16=True)
- **Neden BGE-M3:** Tek encode çağrısıyla dense (1024d) + sparse vektör üretir. İki ayrı model yerine tek model — daha tutarlı. Multilingual (TR+EN). Açık kaynak, lokal çalışır.

### Reranker: BGE-Reranker-v2-m3
- **Neden Reranker:** Bi-encoder (BGE-M3) hızlı ama kaba. Cross-encoder soru+chunk'ı birlikte okuyarak çok daha hassas sıralama yapar. top 20 → top 4.

### Vektör DB: Qdrant (Docker)
- **Neden Qdrant:** Açık kaynak, hybrid search (dense+sparse) native destekli, metadata filtreleme güçlü, Docker ile tek komut kurulum.

### OCR: EasyOCR
- **Neden EasyOCR:** Python-native (pip install), Türkçe + İngilizce desteği güçlü, kurulumu basit. Tesseract alternatif ama sistem bağımlılığı var (apt install). MVP için EasyOCR daha pratik.
- **DEVLOG notu:** "Tesseract'ı da değerlendirdim ama EasyOCR'ın Python-native olması ve Türkçe desteği sebebiyle tercih ettim."

### Chunking: LangChain RecursiveCharacterTextSplitter
- **Parametreler:** chunk_size=500, chunk_overlap=80, separators=["\n\n", "\n", ". ", " ", ""]
- **Context bleeding çözümü:** Başlık tespiti + sınır enjeksiyonu (önceki projemden kanıtlanmış yöntem)

### Retrieval: Hybrid Search + RRF + Reranking
- **Akış:** BGE-M3 encode → Dense search (top 20) + Sparse search (top 20) → RRF merge (k=60) → BGE-Reranker → top 4 chunk
- **Neden hybrid:** Dense semantik anlam yakalar, sparse kelime eşleşmesi yakalar. İkisi birlikte semantic gap'i kapatır.

### UI: Streamlit
- **Neden Streamlit:** MVP için ideal. Hızlı geliştirme. Dosya yükleme + chat + sonuç gösterim tek arayüzde.

## config.py — TÜM PARAMETRELER

```python
import os
from dotenv import load_dotenv
load_dotenv()

# LLM
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# Embedding & Reranker
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")  # Docker service adı
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents")

# Chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))

# Retrieval
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "20"))
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "4"))
RERANK_SCORE_THRESHOLD = float(os.getenv("RERANK_SCORE_THRESHOLD", "0.0"))
RRF_K = int(os.getenv("RRF_K", "60"))

# OCR
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "tr,en").split(",")
```

## KRİTİK TEKNİK DETAYLAR

### 1. Akıllı Belge Yükleme (smart_loader.py)

Dosya tipine göre otomatik yönlendirme:

```
Kullanıcı dosya yükledi
    │
    ├── .pdf uzantısı?
    │   ├── PyMuPDF ile metin çıkar
    │   ├── Metin BOŞ veya çok kısa? (scanned PDF)
    │   │   ├── EVET → Sayfaları resme çevir → EasyOCR → metin
    │   │   └── HAYIR → Normal metin, devam
    │   └── Metadata: kaynak dosya, sayfa no, yöntem (text/ocr)
    │
    ├── .jpg/.jpeg/.png uzantısı?
    │   ├── EasyOCR ile metin çıkar (TR + EN)
    │   └── Metadata: kaynak dosya, yöntem (ocr)
    │
    └── Desteklenmeyen format → Hata mesajı
```

Scanned PDF tespiti: PyMuPDF ile sayfadan metin çıkar, eğer metin uzunluğu < 50 karakter ise "scanned" kabul et, sayfayı pixmap'e çevirip OCR uygula.

### 2. OCR Engine (ocr_engine.py)

```python
import easyocr

class OCREngine:
    def __init__(self, languages=["tr", "en"]):
        # Lazy loading — ilk çağrıda yükle
        self._reader = None
        self._languages = languages
    
    def get_reader(self):
        if self._reader is None:
            self._reader = easyocr.Reader(self._languages, gpu=True)
        return self._reader
    
    def extract_text(self, image_path: str) -> str:
        reader = self.get_reader()
        results = reader.readtext(image_path)
        return "\n".join([text for _, text, conf in results if conf > 0.3])
```

### 3. Context Bleeding Çözümü (preprocessor.py)

Önceki projemden kanıtlanmış yöntem:
- `_satir_baslik_mi()`: 100 char altı + nokta ile bitmiyor + en az 2 kelime + büyük harf/title case + harf oranı >%40
- `_metin_on_isleme()`: Başlıkların etrafına \n\n enjekte et
- RecursiveCharacterTextSplitter \n\n'den öncelikli keser → bölüm sınırları korunur

### 4. Hybrid Search + RRF + Reranking (retrieval/)

RRF formülü: `skor(d) = Σ 1/(k + rank_i)`, k=60
- Her liste için ayrı hesapla, topla. Çarpma değil.
- İki listede de iyi sırada olan chunk en yüksek skor alır.

Score threshold: reranker skoru eşik altındaysa chunk'ı ele. Hiçbir chunk yeterliyse:
→ "Bu konuda yüklenen belgelerde bilgi bulunamadı." (halüsinasyon önleme fallback)

### 5. System Prompt (prompts.py)

```
Sen bir belge analiz asistanısın.
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
{question}
```

### 6. Streaming

Ollama streaming API ile token token cevap üretme. Streamlit'te `st.write_stream()` ile kullanıcı 0.3 saniyede okumaya başlar.

### 7. RAGAS Evaluation (evaluation/ragas_eval.py)

```python
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.metrics import Faithfulness, ResponseRelevancy, ContextPrecision, ContextRecall

# Ollama → RAGAS bağlantısı
client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
ragas_llm = llm_factory(config.OLLAMA_MODEL, provider="openai", client=client)

# 4 metrik
metrics = [Faithfulness(), ResponseRelevancy(), ContextPrecision(), ContextRecall()]
```

Test seti: 15-20 soru-cevap çifti (farklı belge tipleri, farklı diller, halüsinasyon testi dahil)

## STREAMLIT UI TASARIMI (app.py)

### Sol Sidebar:
- Dosya yükleme alanı (PDF, JPG, PNG — çoklu dosya destekli)
- "Belgeri İşle" butonu → yükle, metin çıkar, chunk'la, vektörle, Qdrant'a yaz
- Yüklü belgeler listesi (dosya adı, sayfa sayısı, metin çıkarma yöntemi)
- Model bilgisi (hangi model çalışıyor)

### Ana Alan:
- Chat arayüzü (st.chat_message ile)
- Streaming cevap
- Her cevabın altında kaynak bilgisi (dosya + sayfa)
- "Belge yüklenmedi" durumunda uyarı

### Alt bilgi:
- Sistem durumu (Qdrant bağlantısı, Ollama bağlantısı)

## DOCKER-COMPOSE.yml

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  app:
    build: .
    ports:
      - "8501:8501"
    env_file: .env
    depends_on:
      - qdrant
    volumes:
      - ./data:/app/data
      - model_cache:/root/.cache  # BGE-M3 ve Reranker model cache
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  qdrant_data:
  model_cache:
```

**NOT:** Ollama host makinede çalışır (GPU erişimi). Container'dan host'taki Ollama'ya erişim: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

## DOCKERFILE

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları (EasyOCR için)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

## README.md İÇERİĞİ

1. Proje açıklaması (3-4 cümle)
2. Mimari diyagram (metin tabanlı)
3. Tech stack tablosu (teknoloji + neden seçildi)
4. **Hızlı Başlangıç** (3 adım):
   - `ollama pull qwen2.5:7b-instruct-q4_K_M`
   - `docker compose up --build`
   - Tarayıcıda `http://localhost:8501`
5. **GPU'ya Göre Model Seçim Tablosu:**
   | GPU VRAM | Önerilen Model | Komut |
   |----------|---------------|-------|
   | 16GB+ | qwen2.5:7b-instruct-q4_K_M | `ollama pull qwen2.5:7b-instruct-q4_K_M` |
   | 8GB | qwen2.5:3b | `ollama pull qwen2.5:3b` |
   | 4GB veya CPU | qwen2.5:1.5b | `ollama pull qwen2.5:1.5b` |
   
   Model değiştirmek: `.env` dosyasında `OLLAMA_MODEL=qwen2.5:3b` yapın. Kod değişikliği gerekmez.
6. Konfigürasyon parametreleri tablosu
7. Desteklenen dosya formatları
8. Bilinen sınırlılıklar

## DEVLOG.md FORMATI

Kronolojik, her gün/oturum için:
```markdown
## Gün X: [Başlık] (Y saat)

### Ne Yaptım
- ...

### Karşılaştığım Sorunlar
- ...

### Aldığım Kararlar
- **Karar:** [Ne seçtim]
- **Alternatifler:** [Neleri değerlendirdim]
- **Gerekçe:** [Neden bu yolu seçtim]

### Öğrendiklerim
- ...
```

Her karar için: "ne seçtim + neleri değerlendirdim + neden" üçlüsü. Bu case study'nin en önemli teslimatı.

## TESTING.md FORMATI

```markdown
## Test Senaryoları

### Senaryo X: [Açıklama]
- **Belge:** [dosya adı, tip, dil]
- **Soru:** "..."
- **Beklenen:** ...
- **Sistem Çıktısı:** "..." [gerçek çıktı]
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** ✅ Başarılı / ⚠️ Kısmi / ❌ Başarısız
- **Not:** [varsa açıklama]

### Test Kategorileri:
1. Türkçe PDF — normal metin
2. İngilizce PDF — normal metin
3. Türkçe resim (JPG) — OCR
4. İngilizce resim (PNG) — OCR
5. Scanned PDF (metin katmanı yok) — OCR fallback
6. Tablolu PDF
7. Halüsinasyon testi (belgede olmayan bilgi sorma)
8. Çapraz dil (Türkçe soru, İngilizce belge)
9. Çoklu belge (2+ belge yüklü, doğru belgeden cevap)
10. Belirsiz/kısa soru
```

## ÖNCELİK SIRASI

1. Proje yapısı + config.py + .env
2. document_processing/ (pdf_loader + ocr_engine + smart_loader + preprocessor)
3. indexing/ (chunker + embedder — Qdrant'a yazma)
4. retrieval/ (hybrid_search + rrf + reranker)
5. generation/ (llm + prompts + chain — streaming dahil)
6. app.py (Streamlit UI — dosya yükleme + chat)
7. evaluation/ (RAGAS entegrasyonu)
8. Docker (Dockerfile + docker-compose.yml)
9. tests/ (temel unit testler)
10. README.md + DEVLOG.md + TESTING.md (şablonlar + gerçek içerik)

## KRİTİK KURALLAR (TEKRAR)

- Type hint HER YERDE
- Docstring HER fonksiyona (ne yapıyor, parametreler, dönüş tipi)
- Error handling HER dış çağrıda (Qdrant, Ollama, OCR, dosya okuma)
- Logging önemli adımlarda (dosya yüklendi, OCR tamamlandı, chunk sayısı, retrieval süresi)
- Lazy loading BGE-M3, Reranker, EasyOCR için
- Config'den oku, HARDCODE yapma
- Türkçe + İngilizce her yerde (UI metinleri Türkçe olabilir, kod yorumları İngilizce)
- Her modül bağımsız test edilebilir olsun

## BAŞLA

Sırayla, adım adım ilerle. Her adımı tamamladıktan sonra bir sonrakine geç.
