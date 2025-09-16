import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from tabulate import tabulate

# -------------------------------
# Ayarlar
# -------------------------------
BASE_URL = "https://www.amazon.com.tr/gp/bestsellers/computers/12601907031?pg="
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}
DELAY_RANGE = (2, 5)
MAX_PAGES = 2  # Her sayfada 50 ürün → toplam 100 ürün

# -------------------------------
# Yardımcı Fonksiyonlar
# -------------------------------
def get_soup(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"   Hata {response.status_code} ile {url}")
            return None
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"   İstek sırasında hata: {e}")
        return None

def extract_product_links(soup):
    """Ana sayfadan ürün linklerini çek"""
    links = []
    for li in soup.select("li.zg-no-numbers"):
        a = li.select_one("a.a-link-normal[href*='/dp/']")
        if a:
            href = a["href"].split("?")[0]
            full_link = "https://www.amazon.com.tr" + href
            links.append(full_link)
    return list(dict.fromkeys(links))  # tekrarları kaldır

def extract_product_data(soup, url):
    """Ürün detay sayfasından bilgileri al"""
    data = {}

    # İsim
    data["isim"] = soup.select_one("#productTitle").get_text(strip=True) if soup.select_one("#productTitle") else "NonePublished"

    # Fiyat
    price_sel = "#priceblock_ourprice, #priceblock_dealprice, span.a-price span.a-offscreen"
    data["fiyat"] = soup.select_one(price_sel).get_text(strip=True) if soup.select_one(price_sel) else "NonePublished"

    # Değerlendirilme sayısı
    rating_sel = "#acrCustomerReviewText"
    if soup.select_one(rating_sel):
        try:
            data["değerlendirilme sayısı"] = int(soup.select_one(rating_sel).get_text(strip=True).split()[0].replace(".", ""))
        except:
            data["değerlendirilme sayısı"] = "NonePublished"
    else:
        data["değerlendirilme sayısı"] = "NonePublished"

    # Teknik detaylar
    data["Markası"] = data["Modeli"] = data["Ekran boyutu"] = data["işletim sistemi"] = data["rengi"] = "NonePublished"
    try:
        tables = soup.select("table#productDetails_techSpec_section_1, table#productDetails_detailBullets_sections1")
        for table in tables:
            for row in table.select("tr"):
                th = row.select_one("th")
                td = row.select_one("td")
                if not th or not td:
                    continue
                key = th.get_text(strip=True).lower()
                value = td.get_text(strip=True)
                if "marka" in key:
                    data["Markası"] = value
                elif "model" in key:
                    data["Modeli"] = value
                elif "ekran" in key or "display" in key:
                    data["Ekran boyutu"] = value
                elif "işletim" in key or "operating system" in key:
                    data["işletim sistemi"] = value
                elif "renk" in key or "colour" in key or "color" in key:
                    data["rengi"] = value
    except:
        pass

    # Link ve görsel
    data["link"] = url
    img_tag = soup.select_one("#landingImage, img#imgBlkFront, img.a-dynamic-image")
    data["img"] = img_tag["src"] if img_tag else "NonePublished"

    return data

# -------------------------------
# Ana İş Akışı
# -------------------------------
all_products = []
errors = []

for page in range(1, MAX_PAGES + 1):
    print(f"\n🔎 Sayfa {page} çekiliyor...")
    soup = get_soup(BASE_URL + str(page))
    if not soup:
        errors.append(f"Sayfa {page} çekilemedi")
        continue

    links = extract_product_links(soup)
    print(f"    {len(links)} ürün linki bulundu")

    for idx, link in enumerate(links, 1):
        product_soup = get_soup(link)
        if not product_soup:
            errors.append(f"Ürün çekilemedi: {link}")
            continue
        product_data = extract_product_data(product_soup, link)
        all_products.append(product_data)

        sleep_time = random.uniform(*DELAY_RANGE)
        print(f"       Ürün {idx}/{len(links)} çekildi → {sleep_time:.2f}s bekleniyor...")
        time.sleep(sleep_time)

# -------------------------------
# CSV Kaydı
# -------------------------------
df = pd.DataFrame(all_products)
csv_filename = "amazon_tablets_full.csv"
df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
print(f"\nCSV dosyası kaydedildi: {csv_filename}")

# -------------------------------
# Terminalde tablo olarak göster
# -------------------------------
print("\nÜrün listesi:")
print(tabulate(df, headers="keys", tablefmt="fancy_grid", showindex=True))

# -------------------------------
# Hatalar
# -------------------------------
if errors:
    print("\nHatalar tespit edildi:")
    for e in errors:
        print(" -", e)
else:
    print("\nTüm ürünler başarıyla çekildi")
