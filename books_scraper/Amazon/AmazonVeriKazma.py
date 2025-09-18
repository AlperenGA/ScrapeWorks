#!/usr/bin/env python3
# amazon_tablets_page1_full_clean.py
# Amaç: Amazon Bestseller page=1 içindeki 50 ürünü yakalamak, terminalde sade tablo göstermek.

import requests
import time
import random
import re
import html
import json
from bs4 import BeautifulSoup
import pandas as pd
from tabulate import tabulate

# -------- Ayarlar --------
BASE_URL = "https://www.amazon.com.tr/gp/bestsellers/computers/12601907031"
PAGE_URL = BASE_URL + "?ie=UTF8&pg=1"
HEADERS_BASE = {
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]
DELAY_RANGE = (0.8, 1.6)
RETRIES = 3
DEFAULT_VALUE = "NonePublished"
TARGET_PER_PAGE = 50

session = requests.Session()

# -------- HTTP helper --------
def get(url, retries=RETRIES, timeout=12):
    last_status = None
    for attempt in range(1, retries + 1):
        headers = HEADERS_BASE.copy()
        headers["User-Agent"] = random.choice(USER_AGENTS)
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            last_status = resp.status_code
            if resp.status_code == 200:
                return resp.text, resp.status_code
        except Exception as e:
            print(f"GET exception (attempt {attempt}): {e}")
        time.sleep(0.5 * attempt)
    return "", last_status or 0

# -------- yardımcıler --------
def decode_escaped_payloads(text: str) -> str:
    try:
        unescaped = html.unescape(text)
        decoded = unescaped.encode("utf-8").decode("unicode_escape")
        return decoded
    except Exception:
        return html.unescape(text)

def asin_from_link(link: str):
    m = re.search(r"/dp/([A-Za-z0-9]{8,12})", link)
    return m.group(1) if m else None

# -------- link toplama: DOM rank + payload JSON --------
def collect_products_from_page(raw_html: str, soup: BeautifulSoup, limit=TARGET_PER_PAGE):
    """
    Döndürecek: list of dict { 'rank': '#1', 'link': 'https://.../dp/ASIN', 'asin': 'ASIN' }
    Öncelik: DOM içindeki ürün kartları (rank badge) -- buna güven. Eksikse payload JSON alanlarını kullan.
    """
    products = []
    seen_asins = set()

    # 1) DOM tabanlı: ürün kartları (en güvenilir)
    items = soup.select("div.zg-grid-general-faceout, div.p13n-sc-uncoverable-faceout, div._cDEzb_grid-cell_1uMOS")
    for item in items:
        rank_tag = item.select_one(".zg-bdg-text")
        rank = rank_tag.get_text(strip=True) if rank_tag else DEFAULT_VALUE

        a = item.select_one("a.a-link-normal[href*='/dp/']")
        if not a:
            # bazen href anchor farklı yerde olabilir
            a = item.find("a", href=True)
        if not a:
            continue
        href = a["href"].split("?")[0]
        if href.startswith("/"):
            link = "https://www.amazon.com.tr" + href
        else:
            link = href
        asin = asin_from_link(link)
        if asin and asin not in seen_asins:
            products.append({"rank": rank, "link": link, "asin": asin})
            seen_asins.add(asin)
        if len(products) >= limit:
            return products

    # 2) payload JSON alanları (ör. data-client-recs-list) — ekle, ama sadece eksikse
    # try to find attributes that may contain JSON array of items
    for tag in soup.find_all(lambda t: any(a in t.attrs for a in ("data-client-recs-list", "data-client-recs", "data-a-state", "data-acp-params"))):
        for attr_name in ("data-client-recs-list", "data-client-recs", "data-a-state", "data-acp-params"):
            raw = tag.attrs.get(attr_name)
            if not raw:
                continue
            decoded = decode_escaped_payloads(raw)
            parsed = None
            # try json loads
            for candidate in (decoded, decoded.replace("'", '"')):
                try:
                    parsed = json.loads(candidate)
                    break
                except Exception:
                    parsed = None
            # if parsed is a dict with list under key, try to find list
            if isinstance(parsed, dict):
                # try common keys
                for k in parsed:
                    if isinstance(parsed[k], list):
                        parsed = parsed[k]
                        break

            if isinstance(parsed, list):
                for item in parsed:
                    # item might be dict with 'id' or 'asin'
                    asin = item.get("id") or item.get("asin") if isinstance(item, dict) else None
                    # rank may be in metadataMap.render.zg.rank
                    rank = DEFAULT_VALUE
                    if isinstance(item, dict):
                        mm = item.get("metadataMap", {})
                        rank = mm.get("render.zg.rank") or item.get("rank") or DEFAULT_VALUE
                    if asin:
                        link = f"https://www.amazon.com.tr/dp/{asin}"
                        if asin not in seen_asins:
                            products.append({"rank": rank, "link": link, "asin": asin})
                            seen_asins.add(asin)
                        if len(products) >= limit:
                            return products
            else:
                # fallback: regex ASIN in decoded payload
                for m in re.finditer(r"/dp/([A-Za-z0-9]{8,12})", decoded):
                    asin = m.group(1)
                    if asin not in seen_asins:
                        link = f"https://www.amazon.com.tr/dp/{asin}"
                        products.append({"rank": DEFAULT_VALUE, "link": link, "asin": asin})
                        seen_asins.add(asin)
                        if len(products) >= limit:
                            return products

    # 3) final fallback: raw regex over whole page (in-order)
    decoded_text = decode_escaped_payloads(raw_html)
    for m in re.finditer(r"/dp/([A-Za-z0-9]{8,12})", decoded_text):
        asin = m.group(1)
        if asin not in seen_asins:
            link = f"https://www.amazon.com.tr/dp/{asin}"
            products.append({"rank": DEFAULT_VALUE, "link": link, "asin": asin})
            seen_asins.add(asin)
            if len(products) >= limit:
                break

    return products

# -------- ürün detay çıkarma --------
def extract_product_data(product_html: str, url: str, rank_value: str):
    soup = BeautifulSoup(product_html, "html.parser")
    data = {
        "rank": rank_value,
        "link": url,
        "isim": DEFAULT_VALUE,
        "fiyat": DEFAULT_VALUE,
        "değerlendirilme sayısı": DEFAULT_VALUE,
        "Markası": DEFAULT_VALUE,
        "Modeli": DEFAULT_VALUE,
        "Ekran boyutu": DEFAULT_VALUE,
        "işletim sistemi": DEFAULT_VALUE,
        "rengi": DEFAULT_VALUE,
        "img": DEFAULT_VALUE,
    }

    # isim
    t = soup.select_one("#productTitle, #title, span#productTitle")
    if t:
        data["isim"] = t.get_text(strip=True)

    # fiyat
    for sel in ("#priceblock_ourprice", "#priceblock_dealprice", "span.a-price span.a-offscreen", "#price_inside_buybox", ".a-color-price"):
        p = soup.select_one(sel)
        if p and p.get_text(strip=True):
            data["fiyat"] = p.get_text(strip=True)
            break

    # değerlendirme sayısı
    rc = soup.select_one("#acrCustomerReviewText, #acrCustomerReviewLink, a[href*='product-reviews']")
    if rc and rc.get_text(strip=True):
        num = re.search(r"(\d[\d\.]*)", rc.get_text(strip=True))
        if num:
            try:
                data["değerlendirilme sayısı"] = int(num.group(1).replace(".", ""))
            except Exception:
                data["değerlendirilme sayısı"] = DEFAULT_VALUE

    # teknik detaylar: tablo
    tables = soup.select("table#productDetails_techSpec_section_1, table#productDetails_detailBullets_sections1, table#productDetails_techSpec_section_2")
    for table in tables:
        for row in table.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if not th or not td:
                continue
            key = th.get_text(strip=True).lower()
            val = td.get_text(strip=True)
            if "marka" in key or "brand" in key:
                data["Markası"] = val
            elif "model" in key:
                data["Modeli"] = val
            elif "ekran" in key or "display" in key or "inch" in key:
                data["Ekran boyutu"] = val
            elif "işletim" in key or "operating system" in key:
                data["işletim sistemi"] = val
            elif "renk" in key or "colour" in key or "color" in key:
                data["rengi"] = val

    # detail bullets
    for li in soup.select("#detailBullets_feature_div li"):
        text = li.get_text(" ", strip=True)
        parts = [p.strip() for p in re.split(r":|\n", text) if p.strip()]
        if len(parts) >= 2:
            k = parts[0].lower()
            v = parts[1]
            if "marka" in k or "brand" in k: data["Markası"] = v
            elif "model" in k: data["Modeli"] = v
            elif "ekran" in k or "inch" in k: data["Ekran boyutu"] = v
            elif "işletim" in k or "operating" in k: data["işletim sistemi"] = v
            elif "renk" in k or "color" in k: data["rengi"] = v

    # fallback ekran boyutu (metin içinde)
    if data["Ekran boyutu"] == DEFAULT_VALUE:
        m = re.search(r"(\d{2}\.?(\d)?\s*(inç|inch|\"))", soup.get_text(" ", strip=True), flags=re.IGNORECASE)
        if m:
            data["Ekran boyutu"] = m.group(1)

    # img
    img = soup.select_one("#landingImage, img#imgBlkFront, img.a-dynamic-image, img#main-image, img.s-image")
    if img and img.get("src"):
        data["img"] = img.get("src")

    return data

# -------- terminal gösterim helper (düz tablo) --------
def print_table_plain(df: pd.DataFrame):
    # hide img/link, order columns
    display_df = df.drop(columns=["img", "link"], errors="ignore").fillna(DEFAULT_VALUE)
    preferred = ["rank","isim","fiyat","değerlendirilme sayısı","Markası","Modeli","Ekran boyutu","işletim sistemi","rengi"]
    cols = [c for c in preferred if c in display_df.columns]
    display_df = display_df[cols]
    print("\nÜrün tablosu (img ve link gizlendi):")
    if display_df.empty:
        print(" (veri yok)")
    else:
        print(tabulate(display_df, headers="keys", tablefmt="plain", showindex=False))

# -------- main --------
def main():
    print("Sayfa çekiliyor:", PAGE_URL)
    raw_text, status = get(PAGE_URL)
    if status != 200 or not raw_text:
        print("Sayfa alınamadı. status=", status)
        return

    soup = BeautifulSoup(raw_text, "html.parser")
    products = collect_products_from_page(raw_text, soup, limit=TARGET_PER_PAGE)
    print("Toplam ürün bulundu (unique, hedef 50):", len(products))
    if not products:
        print("Hiç ürün bulunamadı.")
        return

    product_records = []
    errors = []
    for idx, p in enumerate(products, start=1):
        print(f"Çekiliyor ({idx}/{len(products)}) rank={p['rank']} asin={p['asin']}")
        html_text, st = get(p["link"])
        if st != 200 or not html_text:
            print(" Ürün sayfası alınamadı. status=", st)
            errors.append(p["link"])
            time.sleep(random.uniform(*DELAY_RANGE))
            continue
        record = extract_product_data(html_text, p["link"], p["rank"])
        # ensure rank present and ASIN in record
        if "rank" not in record or not record["rank"]:
            record["rank"] = p["rank"]
        product_records.append(record)
        time.sleep(random.uniform(*DELAY_RANGE))

    df = pd.DataFrame(product_records).fillna(DEFAULT_VALUE)
    csv_name = "amazon_tablets_page1_full.csv"
    df.to_csv(csv_name, index=False, encoding="utf-8-sig")
    print("CSV kaydedildi:", csv_name)

    print_table_plain(df)

    if errors:
        print("\nBazı ürünler alınamadı (örnek):")
        for e in errors[:10]:
            print(" -", e)
    else:
        print("\nTüm ürünler alındı.")

if __name__ == "__main__":
    main()
