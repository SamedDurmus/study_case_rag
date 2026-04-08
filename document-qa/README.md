# Belge Analiz & Soru-Cevap Sistemi

PDF ve resim (JPG/PNG) formatındaki belgeleri yükleyip, üzerlerinden Türkçe ve İngilizce doğal dilde soru sorabileceğiniz yapay zeka destekli bir RAG (Retrieval-Augmented Generation) sistemidir. Scanned PDF'ler dahil tüm belge tiplerini destekler. Tamamen lokal çalışır, internet bağlantısı gerektirmez.

## Mimari

```
Kullanıcı (Streamlit UI)
    │
    ├── Belge Yükleme
    │   └── SmartLoader
    │       ├── PDF → PyMuPDF (metin) / EasyOCR (scanned)
    │       └── JPG/PNG → EasyOCR
    │           └── Preprocessor (başlık tespiti + context bleeding çözümü)
    │               └── Chunker (RecursiveCharacterTextSplitter)
    │                   └── Embedder (BGE-M3 dense+sparse)
    │                       └── Qdrant (vektör DB)
    │
    └── Soru-Cevap
        └── RAG Chain
            ├── Hybrid Search (dense + sparse)
            ├── RRF Birleştirme
            ├── Reranker (BGE-Reranker-v2-m3)
            └── LLM (Ollama / Qwen 2.5 7B) → Streaming Cevap
```

## Teknoloji Seçimleri

| Teknoloji | Seçim | Neden |
|-----------|-------|-------|
| LLM | Qwen 2.5 7B Instruct (Q4_K_M) | Türkçe'de güçlü, 7B RAGAS için minimum güvenilir boyut, Q4 ile 4.5GB VRAM |
| LLM Runtime | Ollama | Tek komutla model indirme, air-gapped uyumlu, model değiştirmek tek satır |
| Embedding | BGE-M3 | Tek encode ile dense+sparse, multilingual (TR+EN), açık kaynak |
| Reranker | BGE-Reranker-v2-m3 | Cross-encoder hassas sıralama, top 20 → top 4 |
| Vektör DB | Qdrant | Hybrid search native desteği, Docker ile tek komut kurulum |
| OCR | EasyOCR | Python-native, Türkçe+İngilizce desteği, kolay kurulum |
| Chunking | LangChain RCTS | Başlık sınırı korumalı chunking, context bleeding çözümü |
| UI | Streamlit | Hızlı MVP geliştirme, dosya yükleme + chat tek arayüzde |

## Hızlı Başlangıç

### 1. Ollama modelini indirin
```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
```

### 2. Uygulamayı başlatın
```bash
cp .env.example .env
docker compose up --build
```

### 3. Tarayıcıda açın
```
http://localhost:8501
```

## GPU'ya Göre Model Seçimi

| GPU VRAM | Önerilen Model | Komut |
|----------|---------------|-------|
| 16GB+ | qwen2.5:7b-instruct-q4_K_M | `ollama pull qwen2.5:7b-instruct-q4_K_M` |
| 8GB | qwen2.5:3b | `ollama pull qwen2.5:3b` |
| 4GB veya CPU | qwen2.5:1.5b | `ollama pull qwen2.5:1.5b` |

Model değiştirmek: `.env` dosyasında `OLLAMA_MODEL=qwen2.5:3b` yapın. Kod değişikliği gerekmez.

## Konfigürasyon Parametreleri

| Parametre | Varsayılan | Açıklama |
|-----------|-----------|----------|
| `OLLAMA_MODEL` | qwen2.5:7b-instruct-q4_K_M | Kullanılacak LLM modeli |
| `OLLAMA_BASE_URL` | http://host.docker.internal:11434 | Ollama API adresi |
| `LLM_TEMPERATURE` | 0.0 | LLM yaratıcılık seviyesi (0=deterministik) |
| `LLM_MAX_TOKENS` | 1024 | Maksimum cevap token sayısı |
| `EMBEDDING_MODEL` | BAAI/bge-m3 | Embedding modeli |
| `RERANKER_MODEL` | BAAI/bge-reranker-v2-m3 | Reranker modeli |
| `CHUNK_SIZE` | 500 | Chunk boyutu (karakter) |
| `CHUNK_OVERLAP` | 80 | Chunk örtüşme miktarı (karakter) |
| `RETRIEVAL_TOP_K` | 20 | Hybrid search sonuç sayısı |
| `RERANK_TOP_N` | 4 | Reranker sonrası döndürülen chunk sayısı |
| `RRF_K` | 60 | RRF birleştirme sabiti |

## Desteklenen Dosya Formatları

- **PDF** — Normal metin katmanlı PDF'ler (PyMuPDF ile metin çıkarma)
- **Scanned PDF** — Metin katmanı olmayan PDF'ler (otomatik OCR fallback)
- **JPG/JPEG** — Resim dosyaları (EasyOCR ile metin çıkarma)
- **PNG** — Resim dosyaları (EasyOCR ile metin çıkarma)

## Bilinen Sınırlılıklar

- Tablo yapıları OCR ile sınırlı doğrulukta çıkarılır
- Çok büyük belgeler (100+ sayfa) işleme süresi artabilir
- İlk belge yüklemede BGE-M3 ve EasyOCR modelleri indirilir (~3GB)
- Aynı anda birden fazla kullanıcı desteklenmez (Streamlit session state)
