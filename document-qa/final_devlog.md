# Geliştirme Günlüğü

## Problemi Nasıl Parçaladım

İşe başlamadan önce bir RAG pipeline'ının hangi parçalardan oluştuğunu düşündüm ve projeyi şu modüllere ayırdım:

1. **Belge İşleme** — PDF'den ve resimlerden metin çıkarma, OCR, ön işleme
2. **İndeksleme** — Metni chunk'lara bölme, embedding üretme, vektör veritabanına yazma
3. **Arama** — Hybrid search (dense + sparse), sonuçları birleştirme (RRF), reranking
4. **Cevap Üretme** — LLM'e context ve soru verip cevap alma
5. **Güvenlik** — Prompt injection koruması (input, document, output katmanları)
6. **Değerlendirme** — RAGAS ile otomatik metrik ölçümü
7. **Altyapı** — Docker, Streamlit UI, config yönetimi

Her modülü bağımsız tutmaya çalıştım. Örneğin belge işleme modülü arama modülünü bilmiyor, chain modülü hepsini bir araya getiriyor. Bu sayede bir modülde değişiklik yaparken diğerlerini bozmadan ilerleyebildim.

İlk gün iskelet yapıyı kurdum (10 modül, 24 dosya). İkinci gün entegrasyonları ve güvenlik katmanını ekledim. Üçüncü gün araştırma, analiz ve iyileştirmeler yaptım.

---

## Hangi Yaklaşımları Denedim, Hangisi İşe Yaramadı

### PDF Metin Çıkarma: PyMuPDF → pymupdf4llm

Başta PyMuPDF'in `get_text()` metoduyla düz metin çıkardım. Çalışıyordu ama başlık hiyerarşisi ve tablo yapısı kayboluyordu. LLM'e verilen context düz metin olunca cevap kalitesi düşüyordu.

pymupdf4llm'i araştırdım. Markdown formatında çıktı veriyor — başlıklar `#`, tablolar `| col |` şeklinde korunuyor. LLM'ler Markdown'ı düz metinden çok daha iyi anlıyor. `page_chunks=True` ile sayfa bazlı çıktı da veriyor. Geçiş yaptım, PDF'lerde gözle görülür iyileşme oldu.

Alternatif olarak LlamaParse'ı değerlendirdim ama cloud-based ve ücretli. Unstructured.io da var ama MVP için overkill. pymupdf4llm lokal, hafif ve pymupdf üzerine kurulu — en uygun seçenek.

### OCR: 4 İterasyon Süren Bir Mücadele

Düşük çözünürlüklü bir PNG resimde (674x852px, Raspberry Pi Pico 2 W datasheet sayfası) OCR çok kötü sonuç veriyordu. "Raspberry Pi" → "Raspterry Fi", "4 MB" → "MB" (4 kayıp), "Bluetooth 5.2" → "Bluetocth 5 2" gibi hatalar vardı.

**v1 — Image preprocessing:** Grayscale + upscale (2000px) + kontrast (1.5x) + sharpen ekledim. Genel iyileşme oldu ama rakamlar hâlâ kayıyordu.

**v2 — Daha agresif preprocessing:** Upscale'i 3000px'e çıkardım, kontrastı 2.0x yaptım, binarization ekledim. Bazı kelimeler düzeldi (Bluetooth 5.2, 802.11n) ama binarization ince karakterleri ("4", "W") siliyordu. Global mean threshold anti-aliased ince rakamları beyaza çeviriyordu.

**v3 — Beamsearch decoder:** Binarization'ı kaldırıp EasyOCR'un beamsearch decoder'ını denedim. Daha kötü oldu — satırlar kopuk geldi, cümleler tamamlanmıyordu.

**v4 — Kök sebep tespiti:** Üç iterasyon sonra asıl sorunun preprocessing değil, metin birleştirme olduğunu fark ettim. EasyOCR her text block'u bounding box ile döndürüyor ama sıralama garantisi yok. Eski kod sadece `"\n".join(lines)` yapıyordu. Çözüm: bounding box koordinatlarına göre sıralama, aynı satırdaki blokları birleştirme, noise filtreleme. Bu yaklaşım sorunu büyük ölçüde çözdü.

Bu deneyimden öğrendiğim şey: problemi yanlış yerde arıyordum. Karakter tanıma kalitesini artırmaya çalışırken asıl sorun tanınan karakterlerin doğru sırada birleştirilmemesiydi.

### Scanned PDF'lerde İki Katmanlı Sorun

Doğrudan PNG yükleyince OCR düzgün çalışıyordu ama aynı içeriği PDF'e gömülü resim olarak verince hem scanned tespit hem de OCR kalitesi bozuldu.

**Sorun 1 — Scanned sayfa tespiti:** pymupdf4llm resim içeren sayfalar için `**==> picture [WxH] intentionally omitted <==**` placeholder metni üretiyor. `_clean_text_length()` fonksiyonu Markdown karakterlerini (`#`, `*`, `-`, `|`) temizliyordu ama bu placeholder pattern'ı kalıyordu. Küçük boyutlu resimlerde (ör. `[472 x 447]` → 49 karakter) şans eseri threshold altında kalıyordu. Büyük boyutlu resimlerde (ör. `[1920 x 1080]` → 52 karakter) threshold'u aşıyor, sayfa scanned olarak algılanmıyor, OCR hiç uygulanmıyordu. Regex ile placeholder pattern'ını temizleyerek çözdüm.

**Sorun 2 — Çift interpolasyon:** `extract_page_as_image()` sayfayı `get_pixmap(dpi=300)` ile render ediyordu. Bu, PDF'e gömülü 775x735 boyutundaki resmi sayfa boyutuna (2550x3300) interpolasyonla büyütüyordu. Ardından preprocessing tekrar 3000px'e upscale ediyordu — çift interpolasyon → bulanık → garbled OCR. Render yöntemi 1052 karakter çıkarırken, doğrudan çıkarma 1837 karakter çıkardı. Çözüm: önce `page.get_images()` ile gömülü resmi orijinal piksel verisinden çıkarmayı denemek, başarısızsa render'a fallback yapmak.

### Güvenlik: Regex vs LLM

Input guard'ı regex tabanlı yaptım. İlk versiyonda Türkçe kelimeler false positive verdi — "yıkımından" kelimesindeki "-dan" eki "DAN" jailbreak pattern'i olarak algılandı, "zorunlu" kelimesindeki "run" code injection olarak algılandı. Word boundary (`\b`) ekleyerek çözdüm.

Sonra tam tersi sorun çıktı: İngilizce injection kalıpları yakalanmıyordu. Pattern'ler çok dar tanımlanmıştı. "forget the previous orders" yakalanmıyordu çünkü "orders" listede yoktu. Pattern'leri genişlettim, kelimeler arası `.{0,20}` ile esnek eşleşme ekledim.

LLM tabanlı guard'ı değerlendirdim ama MVP için uygun değil — her sorguda ekstra LLM çağrısı demek, lokal 7B model güvenlik değerlendirmesinde güvenilir değil.

### RAGAS Evaluation: Bellek ve Timeout Sorunları

RAGAS evaluation'ı lokal modelle çalıştırmak beklenenden zor oldu. İki büyük sorun yaşadım:

1. **RAM yetersizliği:** Docker container'da BGE-M3 + Reranker yüklüyken Ollama için yeterli RAM kalmıyordu. Çözüm: evaluation'ı iki aşamaya böldüm — önce RAG cevapları üretilip modeller bellekten atılıyor, sonra RAGAS çalışıyor.

2. **Timeout:** RAGAS 15 örnek × 4 metrik = 60 paralel job çalıştırıyordu. Lokal 7B model bunu kaldıramıyordu. `batch_size=1` ile seri çalıştırma + timeout'u 5 dakikaya çıkarma çözdü.

### System Prompt İyileştirme

İlk system prompt çok basitti — 5 kural, format yönlendirmesi yok. RAGAS answer_relevancy 0.59 geldi (diğer metrikler 0.92+). LLM "Bağlama göre..." gibi dolgu cümleler ekliyordu, cevaplar dağınıktı.

Prompt'a chain-of-thought yönlendirme, cevap formatı talimatları ve güvenlik bölümü ekledim. "Giriş cümlesi kullanma", "tek bilgi soruluyorsa kısa paragraf yaz" gibi spesifik talimatlar verdim.

---

## Kritik Karar Noktaları

### Deterministik Pipeline vs Agent

Agent/tool calling yaklaşımını değerlendirdim ama MVP için deterministik pipeline'ı seçtim. Agent'lar halüsinasyon riski artırır, debug etmesi zorlaşır, latency ekler. Savunma sanayii bağlamında güvenilirlik ve tahmin edilebilirlik daha önemli.

### EasyOCR vs Tesseract

PyMuPDF'in dokümantasyonu Tesseract'tan bahsediyor ve pymupdf4llm'in dahili OCR'u da Tesseract tabanlı. Ancak Tesseract sistem paketi gerektiriyor (`apt install`). EasyOCR Python-native — `pip install` yeterli, Docker'da ekstra dependency yok. Türkçe desteği iyi. Gömülü resim ve taranmış sayfalarda iyi çalışıyor. MVP için en pratik seçenek.

Tablo ağırlıklı belgeler olsa Camelot'u da kullanırdım. OpenDataLoader diye bir kütüphane daha buldum, henüz denemedim ama gelecekte değerlendirilebilir.

### BGE-M3 ile Tek Model Dense+Sparse

Ayrı dense ve sparse model kullanmak yerine BGE-M3'ü seçtim. Tek encode çağrısıyla hem dense (1024d) hem sparse vektör üretiyor. VRAM tasarrufu sağlıyor, kod karmaşıklığı azalıyor. Qdrant native hybrid search desteklediği için entegrasyon kolay oldu.

### Qwen 2.5 7B

3B modelleri önceki projemde test etmiştim — RAGAS internal prompt'larını çözemediler. 7B minimum güvenilir boyut. Qwen 2.5 Türkçe'de LLaMA 7B'den güçlü. Q4 quantization ile 4.5GB VRAM.

### Üç Katmanlı Güvenlik

Sadece input kontrolü indirect injection'ı yakalayamaz (belgeden gelen saldırı). Sadece output kontrolü saldırıyı LLM'e kadar ulaştırır. Üç katman yaptım: input guard kullanıcı sorgusunu kontrol eder, document guard belge yüklenirken tarar, output guard LLM cevabını doğrular.

---

## Nerede Takıldım, Nasıl Çözdüm

### Docker Build Süreleri

Her kod değişikliğinde `docker compose up --build` yapıyordum — torch dahil ~530MB paket her seferinde indiriliyordu. İki çözüm uyguladım:

1. **Pip cache mount:** `--mount=type=cache,target=/root/.cache/pip` ile pip cache build'ler arasında korunuyor. Build süresi ~3 dakikadan ~30 saniyeye düştü.
2. **Volume mount:** Kaynak kodu volume mount ile container'a bağladım. Kod değişikliklerinde rebuild gereksiz, `docker compose restart app` yeterli.

### Versiyon Uyumsuzlukları

Birden fazla kütüphane versiyon sorunu yaşadım:
- `transformers` 4.52+ sürümünde FlagEmbedding'in kullandığı bir fonksiyon kaldırılmış — versiyon sınırı ekledim
- LangChain'de `text_splitter` ayrı pakete taşınmış — import yolunu değiştirdim
- `qdrant-client`'ta `search()` → `query_points()` olmuş — API'yi güncelledim

Bunlardan öğrendiğim: requirements.txt'te versiyon sınırları koymak önemli, "latest" her zaman çalışmıyor.

### BGE-M3 Çift Yükleme

BGE-M3 hem embedder'da hem searcher'da kullanılıyor. İki ayrı instance ~4GB VRAM + 6 dakika ek yükleme süresi demek. `set_model()` ile tek instance'ı paylaştırdım.

### OCR'dan Gelen Bozuk Metin → Yanlış Cevap Zinciri

En zor sorun buydu. 674px genişliğindeki bir PNG resimde OCR "4 MB" yerine "MB" çıkarıyordu (4 kayıp). Retriever bu bozuk chunk yerine PDF'teki "2MB QSPI flash" chunk'ını getiriyordu (daha temiz metin, daha yüksek skor). LLM de "2 MB" diyordu.

Dört iterasyon boyunca preprocessing'i iyileştirmeye çalıştım — upscale, kontrast, binarization, beamsearch decoder. Sonunda kök sebebin preprocessing değil, EasyOCR'un döndürdüğü text block'ların sıralama ve birleştirme mantığı olduğunu fark ettim. Bounding box koordinatlarına göre sıralama ve aynı satırdaki blokları birleştirme ekleyince sorun büyük ölçüde çözüldü.

### PDF Gömülü Resim → OCR Garbled Metin

PNG yükleyince OCR iyi çalışıyordu. Aynı PDF'e resim gömerek test edince "OYUN"→"@YUN", "eşitlik"→"esltllk", "olacaktır"→"oLacakiıf" gibi ağır hatalar çıktı. Sorunun nereden kaynaklandığını bulmak zaman aldı.

İlk düşünce: scanned tespit çalışmıyor. Kontrol ettim — küçük resimler için çalışıyordu ama büyük boyutlu resimler (1920x1080) placeholder text threshold'unu aşıyordu. Bunu fixledim. Ama OCR hâlâ kötüydü.

İkinci sorun: `get_pixmap(dpi=300)` render ederken gömülü küçük resmi (775x735) büyük sayfa boyutuna interpolasyonla geriyor, ardından preprocessing tekrar büyütüyor — çift interpolasyon orijinal piksel verisini tahrip ediyor. `page.get_images()` ile doğrudan çıkarma yaklaşımına geçince 1052 → 1837 karakter iyileşme oldu ve okunamayan kelimeler düzeldi.

---

## Zamanımı Nasıl Harcadım

### Gün 1 (~4 saat)
- Proje yapısı ve modül iskeleti oluşturma
- Tüm modülleri yazma (document_processing, indexing, retrieval, generation, evaluation)
- Streamlit UI, Docker altyapısı, unit testler

### Gün 2 (~3 saat)
- LangSmith entegrasyonu
- RAGAS evaluation scripti
- Güvenlik katmanı (input/document/output guard)
- 17 bug fix (versiyon uyumsuzlukları, Docker sorunları, güvenlik false positive/negative)

### Gün 3 (~3 saat)
- pymupdf4llm araştırması ve geçiş
- OCR preprocessing iterasyonları (4 versiyon)
- System prompt iyileştirme
- Mimari analiz ve dokümantasyon

En çok zaman harcadığım konular: Docker build optimizasyonu, OCR kalitesi iyileştirme ve versiyon uyumsuzlukları. Mimari kararlar ve kod yazma nispeten hızlı gitti.

---

## Baştan Başlasam Neyi Farklı Yapardım

1. **pymupdf4llm'i baştan kullanırdım.** İlk günden Markdown çıktı ile başlamak context kalitesini en baştan yüksek tutardı. Düz `get_text()` ile başlayıp sonra geçiş yapmak zaman kaybıydı.

2. **OCR text reconstruction'ı baştan yazardım.** Üç iterasyon preprocessing'e harcadım ama asıl sorun text block sıralama ve birleştirmeydi. Bounding box bazlı reconstruction'ı ilk günden ekleseydim OCR sorunlarının çoğu daha erken çözülürdü.

3. **Docker volume mount'ları baştan koyardım.** Her değişiklikte rebuild yapmak çok yavaşlattı. Volume mount + pip cache mount'u ilk gün kurardım.

4. **requirements.txt'te versiyon sınırlarını baştan koyardım.** "Latest" ile başlayıp sonra sorun çıkınca sınır eklemek yerine, bilinen çalışan versiyonları baştan pin'lerdim.

5. **RAGAS evaluation'ı iki aşamalı baştan tasarlardım.** 16GB RAM'de embedding + reranker + LLM aynı anda çalışmıyor. Bunu ilk denemede öğrendim ama tasarımı baştan ikiye bölseydim debugging süresi kısalırdı.

6. **Scanned page threshold'unu daha akıllı yapardım.** Sabit 50 karakter yerine font bilgisi kontrolü veya image/metin oranı gibi daha güvenilir yöntemler kullanırdım. Ama MVP için mevcut basit yaklaşım şimdilik yeterli.

---

## Teknik Kararların Özeti

| Karar | Seçilen | Alternatifler | Neden |
|-------|---------|---------------|-------|
| Pipeline tipi | Deterministik RAG | Agent, ReAct | Güvenilirlik, debug edilebilirlik |
| PDF çıkarma | pymupdf4llm (Markdown) | PyMuPDF get_text(), LlamaParse | Yapı koruma, lokal çalışma |
| OCR | EasyOCR | Tesseract, PaddleOCR | Python-native, Docker uyumu |
| Embedding | BGE-M3 (dense+sparse) | Ayrı modeller | Tek model, VRAM tasarrufu |
| Vektör DB | Qdrant | ChromaDB, FAISS | Native hybrid search |
| LLM | Qwen 2.5 7B (Ollama) | LLaMA, Mistral | Türkçe performans |
| Arama | Hybrid + RRF + Reranker | Sadece dense/sparse | Doğruluk |
| Güvenlik | Regex tabanlı (3 katman) | LLM tabanlı guard | Hız, determinizm |
| UI | Streamlit | Gradio, FastAPI+React | MVP hızı |
| Observability | LangSmith | MLflow, W&B | LLM pipeline odaklı |
| Evaluation | RAGAS (4 metrik) | Manuel test | Otomatik, tekrarlanabilir |

## RAGAS Değerlendirme Sonuçları

| Metrik | Skor | Açıklama |
|--------|------|----------|
| Faithfulness | 0.9889 | Cevap context'e sadık mı |
| Answer Relevancy | 0.5982 | Cevap soruyla alakalı mı |
| Context Precision | 0.9222 | Getirilen context doğru mu |
| Context Recall | 1.0000 | Gerekli bilgi getirildi mi |

Answer relevancy düşük olmasının sebeplerini analiz ettim: system prompt yetersiz yönlendirme, LLM'in dolgu cümleler eklemesi, kaynak bilgisi noise yaratması. System prompt iyileştirmesi ile bu skorun artması bekleniyor.

## Bug Fix Özeti

Toplamda 21 bug fix yaptım. Kategorilere göre:

- **Docker/Altyapı (7):** .env eksik, port uyumsuzlukları, build optimizasyonu, volume mount, EasyOCR model indirme
- **Versiyon Uyumsuzlukları (4):** transformers, langchain, qdrant-client, RAGAS deprecation
- **Güvenlik (2):** Regex false positive (Türkçe ekler), false negative (İngilizce pattern eksikliği)
- **Bellek/Performans (3):** BGE-M3 çift yükleme, Ollama RAM yetersizliği, RAGAS timeout
- **OCR/Metin İşleme (4):** Düşük çözünürlüklü resim OCR (4 iterasyon), text block sıralama, pymupdf4llm placeholder scanned tespit hatası, scanned PDF çift interpolasyon
- **Diğer (1):** Temp dosya adı sorunu

---

## Bilinen Sorunlar, Gözlemlenen Hatalar ve İyileştirme Önerileri

Bu bölüm sistemin mevcut sınırlarını, test sırasında gözlemlenen ancak henüz çözülmemiş sorunları ve ileride yapılabilecek geliştirmeleri kapsamaktadır.

---

### 1. Türkçe Soru — İngilizce Belge Retrieval Sorunu

**Ne oluyor?**

Bazı Türkçe sorular İngilizce belgeye karşı doğru chunk'ı bulamıyor. Örneğin:

- `"Flash bellek kapasitesi ne kadardır?"` → "Bu konuda yüklenen belgelerde bilgi bulunamadı."
- `"Raspberry Pi Pico 2 W Flash bellek kapasitesi ne kadardır?"` → "2 MB QSPI flash" ✓
- `"Kart üzerinde güç ve veri iletişimi sağlamak amacıyla hangi bağlantı noktası yer almaktadır?"` → "Bu konuda yüklenen belgelerde bilgi bulunamadı."

**Neden oluyor?**

İki ayrı sebep var:

**Sebep A — Bağlam eksikliği:** "Flash bellek kapasitesi" gibi kısa ve genel sorgular yeterince özgün değil. Sistemde birden fazla belge varsa hangi cihaz veya konu için sorulduğu belli olmadığından embedding benzerlik skoru düşüyor, retrieval başarısız oluyor. Sorguya cihaz adı eklenince (Raspberry Pi Pico 2 W) benzerlik artıyor ve doğru chunk geliyor.

**Sebep B — Dolaylı dil / parafraz:** Belgede "Micro-USB port" yazıyor, kullanıcı ise "güç ve veri iletişimi sağlayan bağlantı noktası" diyor. BGE-M3 cross-lingual retrieval yapabiliyor ama sorgu ne kadar dolaylı ve parafrazlıysa embedding benzerliği o kadar düşüyor. Teknik terimler doğrudan kullanılmadığında (port → bağlantı noktası, USB → data iletişim noktası) chunk eşleşemiyor.

**Olası çözümler:**

| Çözüm | Nasıl çalışır | Maliyet |
|-------|---------------|---------|
| **HyDE (Varsayımsal Cevap Embedding)** | LLM'e "Bu sorunun cevabı belgede nasıl geçer?" diye sorulur, üretilen İngilizce varsayımsal cevap embed edilir, o vektörle retrieval yapılır | Ekstra LLM çağrısı |
| **Sorgu çevirisi** | Türkçe sorgu önce İngilizce'ye çevrilir, İngilizce haliyle retrieval yapılır | Çeviri modeli gerekir |
| **Çoklu sorgu** | Bir sorudan 2-3 farklı yeniden yazım üretilir (farklı kelimelerle), hepsi embed edilip sonuçlar birleştirilerek kullanılır | Ekstra işlem süresi |
| **Kullanıcıya uyarı** | Soru çok kısa veya belirsizse "Hangi belge için soruyorsunuz?" diye sorulur | UI değişikliği |

En pratik kısa vadeli çözüm **sorgu çevirisi**, en doğru ve uzun vadeli çözüm **HyDE**.

---

### 2. Answer Relevancy Skorunun Düşüklüğü (0.60)

**Ne oluyor?**

RAGAS answer_relevancy skoru 0.60 — diğer metrikler 0.92+ olmasına rağmen bu skor belirgin biçimde düşük.

**Neden oluyor?**

Üç somut neden var:

1. **LLM dolgu cümleler ekliyor.** "Bağlamda yer alan bilgiye göre...", "Yüklenen belgelere dayanarak..." gibi başlangıç cümleleri sorunun cevabıyla alakasız. RAGAS bu cümleleri soru-cevap benzerliğini hesaplarken noise olarak algılıyor.

2. **Kaynak bilgisi (citation) skoru düşürüyor.** Cevabın sonuna eklenen `[Kaynak: dosya.pdf, Sayfa: 5]` ifadesi embedding benzerliğini matematiksel olarak azaltıyor — bu metin soruyla alakasız kelimeler içeriyor.

3. **Basit sorulara gereksiz uzun cevap.** "Flash bellek kapasitesi?" gibi tek bilgi sorulan sorulara paragraf uzunluğunda cevap veriliyor.

**Olası çözümler:**

- System prompt'a "Cevaba giriş cümlesi ekleme, doğrudan cevapla başla" talimatı eklemek (kısmen yapıldı, tam çözülmedi).
- Sorunun tipine göre (bilgi sorusu mu, açıklama sorusu mu) cevap uzunluğunu otomatik ayarlamak.
- Kaynak bilgisini cevap metninden ayırarak ayrı bir alana koymak.

---

### 3. ADC Pin Sayısı Hatası (Chunk Sınırı Sorunu)

**Ne oluyor?**

"How many ADC capable pins?" sorusuna sistem sürekli "2" cevabını veriyor, doğru cevap 3.

**Neden oluyor?**

Farklı chunk'larda çelişkili bilgiler var. Bir chunk'ta "GPIO 26 and GPIO 28" yazıyor (2 pin ismi geçiyor), başka bir chunk'ta "three ADC capable pins" yazıyor ama reranker ilk chunk'ı daha yüksek skorla sıralıyor. LLM daha yüksek skorlu chunk'taki "2 pin" bilgisini kullanıyor.

**Olası çözümler:**

- Daha büyük chunk boyutu kullanmak — aynı konudaki bilgilerin tek chunk'a sığma ihtimalini artırır.
- Semantik chunking (karakter sayısına değil, anlam bütünlüğüne göre bölme) uygulamak.
- Birden fazla chunk getirip bunları LLM'e vermek ve "en kapsamlı cevabı bul" demek.

---

### 4. Düşük Çözünürlüklü Resimlerde OCR Sınırları (Hâlâ Mevcut)

**Ne oluyor?**

v4 iyileştirmesiyle büyük ilerleme sağlandı (%14 → %71) ama 674x852px gibi düşük çözünürlüklü resimlerde hâlâ bazı karakterler yanlış okunuyor:
- İnce karakterler: "4", "l", "1", "I" karışabiliyor
- Türkçe özel karakterler: "ş" ↔ "s", "ö" ↔ "o" hataları olabiliyor
- Çok küçük font boyutları tamamen kaybolabiliyor

**Olası çözümler:**

- Tesseract veya PaddleOCR ile karşılaştırmalı test yapmak — bazı karakter tiplerinde daha iyi sonuç verebilir.
- OCR sonrasında LLM ile metin düzeltme (post-processing) eklemek: "Bu garbled metni düzelt" promptuyla OCR çıktısı temizlenebilir.
- Kullanıcıyı uyarmak: Düşük çözünürlüklü dosya yüklenince "OCR doğruluğu sınırlı olabilir" mesajı göstermek.

---

### 5. Scanned Sayfa Tespiti Kırılganlığı

**Ne oluyor?**

Şu anki yöntem: pymupdf4llm çıktısından placeholder metni temizleyip karakter sayısını saymak, 50'den az ise scanned kabul etmek. Bu yaklaşım çalışıyor ama kırılgan.

**Neden sorunlu?**

Eşik (50 karakter) tamamen keyfi seçildi. Bir sayfa hem biraz metin hem de büyük resim içeriyorsa (ör. resimli teknik tablo) yanlış sınıflandırılabilir. pymupdf4llm'in çıktı formatı değişirse placeholder regex bozulabilir.

**Olası çözümler:**

- Sayfa başına düşen resim alanı / toplam sayfa alanı oranına bakmak (örn. %80'den fazla resim alanıysa scanned say).
- pymupdf'in `get_images()` ile resim sayısını ve metin miktarını birlikte değerlendirmek.
- Her iki yöntemi de uygulayıp ikisi de "scanned" diyorsa OCR uygulamak (AND mantığı yerine OR).

---

### 6. Hardcoded Reranker Eşiği

**Ne oluyor?**

Reranker skoru 0.15'in altında kalan chunk'lar filtreleniyor. Bu eşik sabit kodlanmış.

**Neden sorunlu?**

- Bazı sorularda doğru chunk 0.12 skor alıp elenebiliyor (cross-lingual sorgularda bu risk daha yüksek).
- Eşiği düşürünce noise artar, yükseltince doğru chunk'lar elenir.
- Belge tipine göre ideal eşik değişiyor (teknik doküman vs. kural metni).

**Olası çözümler:**

- Eşiği config'e taşımak ve belge tipine göre farklı değer kullanmak.
- Mutlak eşik yerine "en yüksek skoru alan chunk'ın %X'i kadar olan chunk'ları tut" gibi göreceli eşik kullanmak.
- Eşiği kaldırıp her zaman top-K chunk getirmek, ama LLM'e "bu bilgiler yeterli değilse 'bulunamadı' de" demek.

---

### 7. Çoklu Belgede Çapraz Referans Yapılamıyor

**Ne oluyor?**

Sistem her soruda en iyi chunk'ları getiriyor ama bu chunk'lar farklı belgelerden gelebiliyor. Şu an bu normal — ama "Belge A'ya göre X, belge B'ye göre Y nasıl farklılaşıyor?" gibi karşılaştırmalı sorular desteklenmiyor.

**Neden önemli?**

Kullanıcıların çok doğal sorabileceği bir soru tipi: "Bu iki doküman arasında ne fark var?", "İkinci belgede birinci belgeyi destekleyen bir bilgi var mı?" gibi.

**Olası çözüm:**

Sorgu türünü (karşılaştırma mı, tek cevap mı) tespit edip, karşılaştırma sorgularında her belgeden ayrı ayrı chunk getirerek LLM'e "bu iki kaynağı karşılaştır" demek.

---

### 8. Aynı Belgenin Tekrar İndekslenmesi

**Ne oluyor?**

Şu an aynı dosya tekrar yüklenirse yeni chunk'lar oluşturulup koleksiyona ekleniyor. Eski chunk'lar silinmiyor. Bu hem vektör DB'yi şişiriyor hem de aynı bilginin iki kopyası retrieval'da karışıklığa yol açabiliyor.

**Olası çözüm:**

Dosya adı + hash kontrolü yaparak aynı dosya daha önce yüklendiyse "zaten mevcut" demek veya önce ilgili chunk'ları silip sonra yeniden indexlemek.

---

### 9. Tablo İçeren Belgelerde Chunk Bölünmesi

**Ne oluyor?**

pymupdf4llm tabloları Markdown formatında (`| col | col |`) çıkarıyor. Ama tablo büyükse chunk sınırları tablonun ortasından geçebiliyor. LLM yarım tablo alıyor ve yanlış veya eksik cevap verebiliyor.

**Olası çözüm:**

Chunk'lama sırasında Markdown tablo başlangıcı ve bitiş örüntüsünü tespit edip tabloyu bölmemek (tablo farkındalıklı chunking). LangChain'in `MarkdownHeaderTextSplitter`'ı bu konuda yardımcı olabilir.

---

### 10. Streaming Cevap Yok

**Ne oluyor?**

LLM cevabın tamamını üretip gönderiyor. Küçük belgeler ve kısa cevaplar için sorun değil ama uzun cevaplarda kullanıcı hiçbir şey görmeden 10-15 saniye bekliyor.

**Olası çözüm:**

Ollama streaming API'yi destekliyor (`stream=True`). Streamlit'te `st.write_stream()` ile token token göstermek mümkün. Kullanıcı deneyimini önemli ölçüde iyileştirir.

---

### 11. Önbellek (Cache) Yok

**Ne oluyor?**

Aynı soru aynı belgeler için tekrar sorulduğunda sistem baştan embedding üretip retrieval yapıp LLM'e gidiyor. Her şeyi sıfırdan yapıyor.

**Olası çözüm:**

Soru hash'i ve aktif koleksiyon adına göre basit bir in-memory cache (ör. Python dict veya Redis) tutmak. Aynı soru aynı belgeler için tekrar gelirse önbellekten cevap dönmek. LangChain'in `InMemoryCache` veya `SQLiteCache`'i doğrudan entegre edilebilir.

---

### 12. Belge Metadata'sı Filtrelemeye Kapalı

**Ne oluyor?**

Şu an koleksiyona yüklenen tüm belgeler her retrieval'da aday havuzuna giriyor. "Sadece şu PDF'e bak" veya "Sadece Türkçe belgelerde ara" gibi filtreleme yok.

**Neden önemli?**

Çok belgeli senaryolarda kullanıcı hangi belgeden cevap istediğini belirtmek isteyebilir. Örneğin "Periodontal metinde X nedir?" sorusunu teknik datasheete sormaması gerekiyor.

**Olası çözüm:**

Qdrant'ın `filter` özelliğini kullanmak. Belge yüklenirken metadata'ya dosya adı, dil, tarih gibi alanlar eklemek. Sorguda filtreleme parametresi desteklemek.
