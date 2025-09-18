import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from tabulate import tabulate

# -------------------------------
# Ayarlar
# -------------------------------
BASE_URL = "https://www.amazon.com.tr/gp/bestsellers/computers/12601907031/ref=zg_bs_pg_1_computers?ie=UTF8&pg="
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}
DELAY_RANGE = (2, 6)  # istekler arası rastgele delay (saniye)
MAX_PAGES = 5  # örnek olarak ilk 5 sayfa, istenirse arttırılabilir

# -------------------------------
# Yardımcı fonksiyonlar
# -------------------------------
def get_soup(url):
    """URL'den BeautifulSoup objesi döndürür, hata varsa None döner."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"  Hata {response.status_code} ile {url}")
            return None
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"  İstek sırasında hata: {e}")
        return None

def extract_product_links(soup):
    """Ana sayfadaki ürün linklerini döndürür"""
    links = []
    for a in soup.select("div.zg-grid-general-faceout a.a-link-normal"):
        href = a.get("href")
        if href and "/dp/" in href:
            full_link = "https://www.amazon.com.tr" + href.split("?")[0]
            links.append(full_link)
    return list(set(links))  # tekrarları kaldır

def extract_product_data(soup, product_url):
    """Ürün sayfasından istenen bilgileri alır"""
    data = {"link": product_url}  # Link burada kaydediliyor
    
    # Ürün adı
    try:
        data["isim"] = soup.select_one("#productTitle").get_text(strip=True)
    except:
        data["isim"] = None

    # Fiyat
    try:
        price = soup.select_one("#priceblock_ourprice, #priceblock_dealprice, span.a-price span.a-offscreen")
        data["fiyat"] = price.get_text(strip=True) if price else None
    except:
        data["fiyat"] = None

    # Değerlendirme sayısı
    try:
        rating_count = soup.select_one("#acrCustomerReviewText, span[data-asin] .a-size-base.s-underline-text")
        if rating_count:
            data["değerlendirilme sayısı"] = int(rating_count.get_text(strip=True).split()[0].replace(".", "").replace(",", ""))
        else:
            data["değerlendirilme sayısı"] = None
    except:
        data["değerlendirilme sayısı"] = None

    # Ürün detayları için teknik özellikler
    data["Markası"] = data["Modeli"] = data["Ekran boyutu"] = data["işletim sistemi"] = data["rengi"] = None
    try:
        # Teknik detay tabloları
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

        # Bazı ürünlerde detaylar "div#detailBullets_feature_div" altında
        bullets = soup.select("div#detailBullets_feature_div li span.a-text-bold")
        for b in bullets:
            key = b.get_text(strip=True).lower()
            val = b.find_next("span").get_text(strip=True)
            if "marka" in key:
                data["Markası"] = val
            elif "model" in key:
                data["Modeli"] = val
            elif "ekran" in key or "display" in key:
                data["Ekran boyutu"] = val
            elif "işletim" in key or "operating system" in key:
                data["işletim sistemi"] = val
            elif "renk" in key or "colour" in key or "color" in key:
                data["rengi"] = val 
            
    except:
        pass

    return data

# -------------------------------
# Ana iş akışı
# -------------------------------
all_products = []
errors = []

for page in range(1, MAX_PAGES + 1):
    print(f"\n Sayfa {page} çekiliyor...")
    soup = get_soup(BASE_URL + str(page))
    if not soup:
        errors.append(f"Sayfa {page} çekilemedi")
        continue

    links = extract_product_links(soup)
    print(f" {len(links)} ürün linki bulundu")
    
    for idx, link in enumerate(links, 1):
        print(f"   Ürün {idx}/{len(links)}: {link}")
        product_soup = get_soup(link)
        if not product_soup:
            errors.append(f"Ürün çekilemedi: {link}")
            continue
        product_data = extract_product_data(product_soup, link)  # link parametresi eklendi
        all_products.append(product_data)
        sleep_time = random.uniform(*DELAY_RANGE)
        print(f"      {sleep_time:.2f}s bekleniyor...")
        time.sleep(sleep_time)

# -------------------------------
# CSV Kaydı
# -------------------------------
df = pd.DataFrame(all_products)
csv_filename = "amazon_tablets.csv"
df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
print(f"\n CSV dosyası kaydedildi: {csv_filename}")

# -------------------------------
# Terminalde tablo olarak göster
# -------------------------------
print("\n Ürün listesi:")
print(tabulate(df, headers="keys", tablefmt="fancy_grid", showindex=True))

# -------------------------------
# Hatalar
# -------------------------------
if errors:
    print("\n  Hatalar tespit edildi:")
    for e in errors:
        print(" -", e)
else:
    print("\n Tüm ürünler başarıyla çekildi")
