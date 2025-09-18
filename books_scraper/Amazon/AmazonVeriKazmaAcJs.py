import requests
from bs4 import BeautifulSoup
import pandas as pd
from tabulate import tabulate
import time
import random

# -------------------------------
# Ayarlar
# -------------------------------
ACP_URL = "https://www.amazon.com.tr/acp/p13n-zg-list-grid-desktop/p13n-zg-list-grid-desktop-bdc0acef-3f77-4e43-aee1-ea9a71dd87a4-1757615436250/nextPage?page-type=zeitgeist&stamp=1758011958685"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}
DELAY_RANGE = (1, 2)

# -------------------------------
# ACP HTML parse ile ürünleri çek
# -------------------------------
def get_products_from_acp_html(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Hata {response.status_code} ile {url}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        products = []

        for li in soup.select("li.zg-no-numbers"):
            asin = li.select_one("div[data-asin]")["data-asin"] if li.select_one("div[data-asin]") else None
            title = li.select_one("._cDEzb_p13n-sc-css-line-clamp-4_2q2cc")
            price = li.select_one("._cDEzb_p13n-sc-price_3mJ9Z")
            link = li.select_one("a.a-link-normal")["href"] if li.select_one("a.a-link-normal") else None
            img = li.select_one("img")["src"] if li.select_one("img") else None

            products.append({
                "rank": li.select_one(".zg-bdg-text").get_text(strip=True) if li.select_one(".zg-bdg-text") else "NonePublished",
                "title": title.get_text(strip=True) if title else "NonePublished",
                "price": price.get_text(strip=True) if price else "NonePublished",
                "link": f"https://www.amazon.com.tr{link}" if link else "NonePublished",
                "img": img if img else "NonePublished",
                "asin": asin if asin else "NonePublished"
            })

        return products
    except Exception as e:
        print("İstek/parsing hatası:", e)
        return []

# -------------------------------
# Ürün sayfasından teknik detaylar
# -------------------------------
def get_product_details(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {}
        soup = BeautifulSoup(response.text, "html.parser")
        details = {
            "Markası": "NonePublished",
            "Modeli": "NonePublished",
            "Ekran boyutu": "NonePublished",
            "işletim sistemi": "NonePublished",
            "rengi": "NonePublished"
        }
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
                    details["Markası"] = value
                elif "model" in key:
                    details["Modeli"] = value
                elif "ekran" in key or "display" in key:
                    details["Ekran boyutu"] = value
                elif "işletim" in key or "operating system" in key:
                    details["işletim sistemi"] = value
                elif "renk" in key or "colour" in key or "color" in key:
                    details["rengi"] = value
        return details
    except Exception as e:
        print(f"Hata {url}: {e}")
        return {}

# -------------------------------
# Ana iş akışı
# -------------------------------
all_products = []
products = get_products_from_acp_html(ACP_URL)
print(f"{len(products)} ürün bulundu.")

for idx, prod in enumerate(products, 1):
    print(f"\n🔎 Ürün {idx} çekiliyor: {prod['link']}")
    details = get_product_details(prod["link"])
    merged = {**prod, **details}  # ACP HTML + ürün sayfası detaylarını birleştir
    all_products.append(merged)
    time.sleep(random.uniform(*DELAY_RANGE))

# -------------------------------
# CSV ve tablo
# -------------------------------
df = pd.DataFrame(all_products)
csv_filename = "amazon_tablets_full.csv"
df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
print(f"\nCSV dosyası kaydedildi: {csv_filename}")

print("\nÜrün listesi:")
print(tabulate(df, headers="keys", tablefmt="fancy_grid", showindex=True))
