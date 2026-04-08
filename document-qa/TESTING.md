# Test Senaryoları ve Sonuçlar

## Test Kategorileri

### Senaryo 1: Türkçe PDF — Normal Metin
- **Belge:** [belge adı, PDF, Türkçe]
- **Soru:** "..."
- **Beklenen:** ...
- **Sistem Çıktısı:** "..." 
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 2: İngilizce PDF — Normal Metin
- **Belge:** [belge adı, PDF, İngilizce]
- **Soru:** "..."
- **Beklenen:** ...
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 3: Türkçe Resim (JPG) — OCR
- **Belge:** [belge adı, JPG, Türkçe]
- **Soru:** "..."
- **Beklenen:** ...
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 4: İngilizce Resim (PNG) — OCR
- **Belge:** [belge adı, PNG, İngilizce]
- **Soru:** "..."
- **Beklenen:** ...
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 5: Scanned PDF — OCR Fallback
- **Belge:** [belge adı, scanned PDF]
- **Soru:** "..."
- **Beklenen:** ...
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 6: Tablolu PDF
- **Belge:** [belge adı, PDF, tablo içerikli]
- **Soru:** "..."
- **Beklenen:** ...
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 7: Halüsinasyon Testi
- **Belge:** [herhangi bir yüklü belge]
- **Soru:** "Belgede olmayan bir konu hakkında soru"
- **Beklenen:** "Bu konuda yüklenen belgelerde bilgi bulunamadı."
- **Sistem Çıktısı:** "..."
- **Kaynak:** —
- **Değerlendirme:** Bekliyor
- **Not:** Sistemin kendi bilgisinden ekleme yapmaması bekleniyor

### Senaryo 8: Çapraz Dil (Türkçe Soru, İngilizce Belge)
- **Belge:** [İngilizce belge]
- **Soru:** "Türkçe soru"
- **Beklenen:** Türkçe cevap
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 9: Çoklu Belge
- **Belge:** [2+ belge yüklü]
- **Soru:** "Belirli bir belgedeki bilgiyi soran soru"
- **Beklenen:** Doğru belgeden cevap + doğru kaynak gösterimi
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

### Senaryo 10: Belirsiz/Kısa Soru
- **Belge:** [herhangi bir yüklü belge]
- **Soru:** "Ne diyor?"
- **Beklenen:** Genel bir özet veya en alakalı bilgi
- **Sistem Çıktısı:** "..."
- **Kaynak:** [dosya, sayfa]
- **Değerlendirme:** Bekliyor
- **Not:** —

## RAGAS Değerlendirme Sonuçları

| Metrik | Skor | Açıklama |
|--------|------|----------|
| Faithfulness | — | Cevabın context'e sadakati |
| Response Relevancy | — | Cevabın soruya uygunluğu |
| Context Precision | — | Alınan context'lerin doğruluğu |
| Context Recall | — | Gerekli bilgilerin ne kadarı alındı |

*Sonuçlar gerçek test çalıştırmaları sonrasında doldurulacak.*
