# Belge Analiz & Soru-Cevap Sistemi

PDF ve resim (JPG/PNG) formatındaki belgeleri yükleyip, üzerlerinden Türkçe ve İngilizce doğal dilde soru sorabileceğiniz yapay zeka destekli bir RAG sistemidir. Scanned PDF'ler dahil tüm belge tiplerini destekler. Tamamen lokal çalışır, internet bağlantısı gerektirmez.

## Nasıl Çalışır

Yüklenen belge parçalara bölünür, her parça vektöre dönüştürülür ve veritabanına kaydedilir. Soru geldiğinde ilgili parçalar bulunur, bir araya getirilerek LLM'e verilir ve cevap üretilir.

```
Belge → Metin Çıkarma (PDF/OCR) → Parçalama → Vektör DB (Qdrant)
Soru  → Arama (Hybrid) → Sıralama (Reranker) → LLM → Cevap
```

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
http://localhost:5050
```

İlk başlatmada BGE-M3 ve EasyOCR modelleri otomatik indirilir (~3GB).

## GPU'ya Göre Model Seçimi

| GPU VRAM | Önerilen Model | Komut |
|----------|---------------|-------|
| 16GB+ | qwen2.5:7b-instruct-q4_K_M | `ollama pull qwen2.5:7b-instruct-q4_K_M` |
| 8GB | qwen2.5:3b | `ollama pull qwen2.5:3b` |
| 4GB veya CPU | qwen2.5:1.5b | `ollama pull qwen2.5:1.5b` |

Model değiştirmek için `.env` dosyasında `OLLAMA_MODEL` değerini güncelleyin. Kod değişikliği gerekmez.

## Desteklenen Dosya Formatları

- **PDF** — Metin katmanlı PDF (pymupdf4llm)
- **Scanned PDF** — Metin katmanı olmayan, taranmış PDF (otomatik OCR)
- **JPG / PNG** — Resim dosyaları (EasyOCR)

## Teknoloji Seçimleri

| Bileşen | Seçim | Neden |
|---------|-------|-------|
| LLM | Qwen 2.5 7B (Q4_K_M) | Türkçe performansı, 4.5GB VRAM |
| LLM Runtime | Ollama | Lokal, model değiştirmek tek satır |
| Embedding | BGE-M3 | Dense + sparse tek modelde, çok dilli |
| Reranker | BGE-Reranker-v2-m3 | Hassas sıralama, top 20 → top 4 |
| Vektör DB | Qdrant | Hybrid search native desteği |
| OCR | EasyOCR | Python-native, Türkçe + İngilizce |
| UI | Streamlit | Hızlı prototip, dosya yükleme + chat |

## Konfigürasyon

`.env` dosyasında değiştirilebilecek başlıca parametreler:

| Parametre | Varsayılan | Açıklama |
|-----------|-----------|----------|
| `OLLAMA_MODEL` | qwen2.5:7b-instruct-q4_K_M | LLM modeli |
| `LLM_TEMPERATURE` | 0.0 | 0 = deterministik cevap |
| `LLM_MAX_TOKENS` | 1024 | Maksimum cevap uzunluğu |
| `CHUNK_SIZE` | 500 | Parça boyutu (karakter) |
| `CHUNK_OVERLAP` | 80 | Parçalar arası örtüşme |
| `RETRIEVAL_TOP_K` | 20 | Arama sonucu sayısı |
| `RERANK_TOP_N` | 4 | Reranker sonrası kullanılan parça sayısı |

## Test Dosyaları !!! ÖNEMLİ !!!

`data/test_documents/` klasöründe sistemi hemen denemek için hazır belgeler ve soru-cevap çiftleri bırakıldı:

| Dosya | Tip | Dil |
|-------|-----|-----|
| `perio_part1.pdf` | PDF (metin) | Türkçe |
| `pico-2-w-datasheet.pdf` | PDF (metin) | İngilizce |
| `basket_kurallar.pdf` | Scanned PDF | Türkçe |
| `futbol_kural_1.jpg`, `futbol_kural_2.png` | Resim | Türkçe |
| `picow2_firstpage.png`, `picow2_secondpage.png` | Resim | İngilizce |

Her belge için hazır soru-cevap çiftleri de aynı klasörde `.json` ve `.md` formatında mevcut (`perio_qa_pairs.json`, `futbol_qa_pairs.json` vb.). Sistemi test ederken bu soruları kullanabilir, beklenen cevaplarla karşılaştırabilirsiniz.

## Bilinen Sınırlılıklar

- Düşük çözünürlüklü resimlerde (674x852px gibi) OCR doğruluğu %100 garanti edilemez
- Çok dolaylı veya bağlamsız kısa sorgularda retrieval başarısı düşebilir
- Çok büyük belgeler (100+ sayfa) işleme süresi artabilir
- Aynı anda birden fazla kullanıcı desteklenmez
