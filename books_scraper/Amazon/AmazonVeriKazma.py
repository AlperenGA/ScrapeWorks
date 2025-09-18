#!/usr/bin/env python3
# amazon_tablets_page1_full.py
# Amaç: tek Amazon bestseller sayfasından (page=1) 50 ürünü yakalamak (payload + regex + selectors)
# Eksik alanlar "NonePublished" stringi ile doldurulur.
# Terminalde "img" ve "link" sütunları gösterilmez (CSV'ye kaydedilir).

import requests
from bs4 import BeautifulSoup
import pandas as pd
from tabulate import tabulate
import time
import random
import html
import re
import json
from typing import List, Dict, Tuple

# -------------------------------
# Ayarlar
# -------------------------------
BASE_URL = "https://www.amazon.com.tr/gp/bestsellers/computers/12601907031"
PAGE_URL = BASE_URL + "?ie=UTF8&pg=1"
HEADERS_BASE = {
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}
# Küçük user-agent rotasyonu (basit, örnek)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]
DELAY_RANGE = (0.8, 1.6)
MAX_WORKERS = 5
RETRIES = 3
DEFAULT_VALUE = "NonePublished"
TARGET_PER_PAGE = 50

session = requests.Session()


# -------------------------------
# HTTP helpers
# -------------------------------
def get(url: str, retries: int = RETRIES, timeout: int = 12) -> Tuple[str, int]:
    """GET isteği, basit retry ve user-agent rotasyonu. Döner: (response_text, status_code)"""
    last_status = None
    for attempt in range(1, retries + 1):
        headers = HEADERS_BASE.copy()
        headers["User-Agent"] = random.choice(USER_AGENTS)
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            last_status = resp.status_code
            if resp.status_code == 200:
                return resp.text, resp.status_code
            else:
                print(f"   ⚠️  GET status {resp.status_code} (attempt {attempt}) for {url}")
        except Exception as e:
            print(f"   ⚠️  GET exception (attempt {attempt}): {e}")
        time.sleep(0.5 * attempt)
    return "", last_status or 0


# -------------------------------
# Link toplama - çeşitli yöntemler
# -------------------------------
def regex_extract_asins_from_text(text: str) -> List[str]:
    """
    Regex ile sayfa textinden ASIN'leri sırayla yakala:
    - /dp/ASIN
    - /gp/product/ASIN
    Bu, payload içinde escaped/encoded olmayan formları yakalar.
    """
    found = []
    # case-insensitive ASIN pattern (ASIN genellikle 10 chars but sometimes 10, keep 8-12 range)
    patterns = [r"/dp/([A-Za-z0-9]{8,12})", r"/gp/product/([A-Za-z0-9]{8,12})"]
    for pat in patterns:
        for m in re.finditer(pat, text):
            asin = m.group(1)
            link = f"https://www.amazon.com.tr/dp/{asin}"
            found.append(link)
    return found


def decode_escaped_payloads(text: str) -> str:
    """
    HTML unescape ve unicode escape decode denemesi:
    Payload'lar bazen \u003d gibi escape'li olur -> bunları çözmek gerekebilir.
    """
    try:
        unescaped = html.unescape(text)
        # unicode_escape decode: '\u003d' -> '=' gibi
        decoded = unescaped.encode("utf-8").decode("unicode_escape")
        return decoded
    except Exception:
        # fallback
        return html.unescape(text)


def extract_from_anchors(soup: BeautifulSoup) -> List[str]:
    """DOM içindeki anchor'lardan /dp/ veya gp/product linklerini al."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # normalize relative links
        # check common patterns
        if "/dp/" in href or "/gp/product/" in href:
            href_clean = href.split("?")[0]
            if href_clean.startswith("/"):
                href_clean = "https://www.amazon.com.tr" + href_clean
            links.append(href_clean)
    return links


def extract_from_data_asin(soup: BeautifulSoup) -> List[str]:
    """data-asin attribute'larından link oluştur."""
    links = []
    for tag in soup.select("[data-asin]"):
        asin = tag.get("data-asin")
        if asin and asin.strip():
            links.append(f"https://www.amazon.com.tr/dp/{asin.strip()}")
    return links


def extract_from_raw_payload_attributes(soup: BeautifulSoup) -> List[str]:
    """
    raw-html[data-payload] veya benzeri data-payload attribute'larını alıp decode ederek içinden /dp/ link çıkar.
    """
    links = []
    # örnek attribute isimleri: data-payload, data-a-state, data-client-recs-list, data-client-recs
    attrs_to_try = ["data-payload", "data-client-recs-list", "data-a-state", "data-asin", "data-data", "data"]
    # raw-html tagleri
    for tag in soup.find_all(lambda t: any(attr in t.attrs for attr in attrs_to_try)):
        for attr in attrs_to_try:
            if attr in tag.attrs:
                raw = tag.attrs.get(attr, "")
                if not raw:
                    continue
                # decode raw string
                text = decode_escaped_payloads(raw)
                # find asins inside decoded
                found = regex_extract_asins_from_text(text)
                for l in found:
                    links.append(l)
    return links


def collect_links_ordered(raw_html: str, soup: BeautifulSoup, limit: int = TARGET_PER_PAGE) -> List[str]:
    """
    En güçlü yöntem: önce decode edilmiş sayfa text üzerinden regex ile /dp/ occurrence'larını sırayla al.
    Sonra DOM tabanlı yöntemlerle yedekle (anchors, data-asin, payload attrs).
    """
    links_ordered = []
    seen = set()

    # 1) Decode page so payload escapes are resolved
    decoded_text = decode_escaped_payloads(raw_html)

    # 2) Main regex pass (in-order)
    for m in re.finditer(r"/dp/([A-Za-z0-9]{8,12})", decoded_text):
        asin = m.group(1)
        link = f"https://www.amazon.com.tr/dp/{asin}"
        if link not in seen:
            links_ordered.append(link)
            seen.add(link)
            if len(links_ordered) >= limit:
                return links_ordered

    # Also try gp/product pattern in-order
    for m in re.finditer(r"/gp/product/([A-Za-z0-9]{8,12})", decoded_text):
        asin = m.group(1)
        link = f"https://www.amazon.com.tr/dp/{asin}"
        if link not in seen:
            links_ordered.append(link)
            seen.add(link)
            if len(links_ordered) >= limit:
                return links_ordered

    # 3) DOM anchor pass (supplement)
    for link in extract_from_anchors(soup):
        if link not in seen:
            links_ordered.append(link)
            seen.add(link)
            if len(links_ordered) >= limit:
                return links_ordered

    # 4) data-asin attributes pass
    for link in extract_from_data_asin(soup):
        if link not in seen:
            links_ordered.append(link)
            seen.add(link)
            if len(links_ordered) >= limit:
                return links_ordered

    # 5) raw payload attributes (JSON/HTML encoded in attributes)
    for link in extract_from_raw_payload_attributes(soup):
        if link not in seen:
            links_ordered.append(link)
            seen.add(link)
            if len(links_ordered) >= limit:
                return links_ordered

    # 6) final regex fallback on raw_html (catch anything missed)
    for m in re.finditer(r"([A-Za-z0-9\-]*?/dp/[A-Za-z0-9]{8,12})", decoded_text):
        link_part = m.group(1)
        if link_part.startswith("/"):
            link = "https://www.amazon.com.tr" + link_part.split("?")[0]
        else:
            link = link_part.split("?")[0]
        if link not in seen:
            links_ordered.append(link)
            seen.add(link)
            if len(links_ordered) >= limit:
                return links_ordered

    return links_ordered


# -------------------------------
# Ürün detay çıkarma (geliştirilmiş)
# -------------------------------
def extract_product_data(product_html: str, url: str) -> Dict[str, str]:
    """Ürün detaylarını alır (birçok selector denemesi)."""
    soup = BeautifulSoup(product_html, "html.parser")
    data = {
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

    # fiyat -> deneme sırası
    price_selectors = [
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "span.a-price span.a-offscreen",
        "#price_inside_buybox",
        ".a-color-price"
    ]
    for sel in price_selectors:
        p = soup.select_one(sel)
        if p and p.get_text(strip=True):
            data["fiyat"] = p.get_text(strip=True)
            break

    # değerlendirme sayısı
    rc = soup.select_one("#acrCustomerReviewText, #acrCustomerReviewLink, a[href*='product-reviews']")
    if rc and rc.get_text(strip=True):
        try:
            # first number in the string
            num = re.search(r"(\d[\d\.]*)", rc.get_text(strip=True))
            if num:
                data["değerlendirilme sayısı"] = int(num.group(1).replace(".", ""))
        except Exception:
            pass

    # birçok yerde olabilecek teknik bilgiler - tablo veya detay listesi
    # 1) productDetails tables
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

    # 2) detail bullets (bazı sayfalarda)
    bullet_section = soup.select_one("#detailBullets_feature_div, #detailBullets_feature_div .content, .detail-bullet-list")
    if bullet_section:
        for li in bullet_section.select("li"):
            text = li.get_text(" ", strip=True)
            # örnek: "Marka: Samsung"
            parts = [p.strip() for p in re.split(r":|\n", text) if p.strip()]
            if len(parts) >= 2:
                key = parts[0].lower()
                val = parts[1]
                if "marka" in key or "brand" in key:
                    data["Markası"] = val
                elif "model" in key:
                    data["Modeli"] = val
                elif "ekran" in key or "inch" in key:
                    data["Ekran boyutu"] = val
                elif "işletim" in key or "operating" in key:
                    data["işletim sistemi"] = val
                elif "renk" in key or "color" in key:
                    data["rengi"] = val

    # 3) fallback: metin tabanlı arama (kaba ama faydalı)
    full_text = soup.get_text(" ", strip=True)
    # örnek pattern "Ekran: 10.1\""
    screen_match = re.search(r"(\d{2}\.?(\d)?\s*(inç|inch|\"))", full_text, flags=re.IGNORECASE)
    if screen_match and data["Ekran boyutu"] == DEFAULT_VALUE:
        data["Ekran boyutu"] = screen_match.group(1)

    # görsel
    img = soup.select_one("#landingImage, img#imgBlkFront, img.a-dynamic-image, img#main-image, img.s-image")
    if img and img.get("src"):
        data["img"] = img.get("src")

    return data


# -------------------------------
# Ana akış
# -------------------------------
def main():
    print(f"\n🔎 Sayfa 1 çekiliyor: {PAGE_URL}")
    raw_text, status = get(PAGE_URL)
    if status != 200 or not raw_text:
        print(f"❌ Sayfa alınamadı (status={status}). Çalışma durduruldu.")
        return

    # parse soup
    soup = BeautifulSoup(raw_text, "html.parser")

    # LOG: hangi yöntemlerden kaç link çıkıyor (ön bilgi)
    # (1) regex on decoded text
    decoded_text = decode_escaped_payloads(raw_text)
    regex_links = regex_extract_asins_from_text(decoded_text)
    anchors_links = extract_from_anchors(soup)
    data_asin_links = extract_from_data_asin(soup)
    payload_attr_links = extract_from_raw_payload_attributes(soup)

    print(f"   Link özet (ara yüz): regex:{len(regex_links)} anchors:{len(anchors_links)} data-asin:{len(data_asin_links)} payload-attrs:{len(payload_attr_links)}")

    #  Sıraya göre link topla (öncelik: regex-order, sonra anchor, data-asin, payloadAttrs)
    links = collect_links_ordered(raw_html=raw_text, soup=soup, limit=TARGET_PER_PAGE)
    print(f"   Toplam unique link (sıraya göre, limit {TARGET_PER_PAGE}): {len(links)}")

    if not links:
        print("⚠️ Hiç link bulunamadı. Sayfa yapısı beklenenden farklı olabilir.")
        return

    # debug: eğer < TARGET_PER_PAGE ise, yazdır ilk 80 link (debug)
    if len(links) < TARGET_PER_PAGE:
        print("⚠️ Uyarı: hedef 50'e ulaşılmadı. Bulunan linkler (ilk 80):")
        for i, l in enumerate(links[:80], 1):
            print(f"  {i:02d}. {l}")

    # Ürün sayfalarını paralel çek (kademeli delay)
    product_records = []
    errors = []
    for idx, link in enumerate(links, start=1):
        print(f"\n📥 Ürün {idx}/{len(links)} çekiliyor: {link}")
        html_text, st = get(link)
        if st != 200 or not html_text:
            print(f"   ⚠️ Ürün sayfası alınamadı (status={st})")
            errors.append(link)
            # küçük gecikme ve devam
            time.sleep(random.uniform(*DELAY_RANGE))
            continue

        record = extract_product_data(html_text, link)
        product_records.append(record)
        # rastgele gecikme
        time.sleep(random.uniform(*DELAY_RANGE))

    # CSV kaydet
    df = pd.DataFrame(product_records)
    df = df.fillna(DEFAULT_VALUE)
    csv_name = "amazon_tablets_page1_full.csv"
    df.to_csv(csv_name, index=False, encoding="utf-8-sig")
    print(f" CSV kaydedildi: {csv_name}")

    # Terminal gösterimi: img ve link sütunlarını gizle
    display_df = df.copy()
    for c in ("img", "link"):
        if c in display_df.columns:
            display_df.drop(columns=[c], inplace=True)

    print(" Terminalde gösterilen ürün tablosu (img ve link gizlendi):")
    if not display_df.empty:
        print(tabulate(display_df, headers="keys", tablefmt="fancy_grid", showindex=True))
    else:
        print("   (veri yok)")

    # Hatalar raporu
    if errors:
        print(" Bazı ürünler alınamadı (örnek):")
        for e in errors[:10]:
            print(" -", e)
    else:
        print(" Tüm ürün sayfaları başarılı şekilde alındı.")


if __name__ == "__main__":
    main()
