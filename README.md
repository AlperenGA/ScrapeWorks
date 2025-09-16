# 📚 books_scraper

**books_scraper**, Python ile yazılmış bir web kazıyıcıdır. Bu araç, kitap verilerini çeşitli web sitelerinden toplar ve düzenler.

## 🚀 Özellikler

- **Veri Çekme**: Kitap başlıkları, yazarlar, fiyatlar, değerlendirmeler ve daha fazlasını toplar.
- **Çok Sayfalı Dolaşım**: Birden fazla sayfayı otomatik olarak işler.
- **Veri Formatları**: Toplanan verileri CSV veya JSON formatlarında kaydeder.
- **Veri Analizi**: Toplanan veriler üzerinde temel analizler yapabilir.

## 🛠️ Gereksinimler

- Python 3.x
- Gerekli kütüphaneler:
  - `requests`
  - `selenium`
  - `scrapy`
  - `beautifulsoup4`
  - `pandas`

## 📥 Karşılaştırma ve Kazanım


| Teknoloji         | Avantajlar                                        | Dezavantajlar                      | Kullanım Alanı                              |
| ----------------- | ------------------------------------------------- | ---------------------------------- | ------------------------------------------- |
| **Scrapy**        | Hızlı, paralel istek, büyük projeler              | Öğrenme eğrisi, dinamik içerik zor | Statik, büyük ve çok sayfalı siteler        |
| **BeautifulSoup** | Basit, kolay öğrenilir, küçük projeler için ideal | Çok sayfa ve JS yönetimi zayıf     | Küçük, tek sayfa veya basit veri çekme      |
| **Selenium**      | Dinamik, JS destekli, etkileşimli                 | Ağır, yavaş, kaynak yoğun          | JS ile yüklenen, etkileşim gereken sayfalar |

