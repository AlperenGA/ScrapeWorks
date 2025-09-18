import pandas as pd
from tabulate import tabulate

# -------------------------------
# CSV dosyalarını yükle
# -------------------------------
old_csv = "amazon_tablets.csv"         # Eski sürüm CSV
new_csv = "amazon_tablets_page1_2_full.csv"    # FALLBACK + Payload tabanlı yeni sürüm CSV

df_old = pd.read_csv(old_csv)
df_new = pd.read_csv(new_csv)

# -------------------------------
# Eksik alanlar ve NonePublished kontrolü
# -------------------------------
for col in df_new.columns:
    df_new[col] = df_new[col].fillna("NonePublished")
for col in df_old.columns:
    df_old[col] = df_old[col].fillna("NonePublished")

# -------------------------------
# Karşılaştırma
# -------------------------------
comparison = []

# Ortak linkleri bul
common_links = set(df_old['link']).intersection(set(df_new['link']))

for link in common_links:
    old_row = df_old[df_old['link'] == link].iloc[0]
    new_row = df_new[df_new['link'] == link].iloc[0]

    differences = {}
    for col in df_new.columns:
        old_val = str(old_row[col]) if col in df_old.columns else "N/A"
        new_val = str(new_row[col])
        if old_val != new_val:
            differences[col] = {"old": old_val, "new": new_val}

    if differences:
        comparison.append({"link": link, "differences": differences})

# -------------------------------
# Terminalde tablo şeklinde göster
# -------------------------------
if comparison:
    table_data = []
    for comp in comparison:
        link = comp["link"]
        for col, vals in comp["differences"].items():
            table_data.append([link, col, vals["old"], vals["new"]])

    print("\nÜrünlerdeki değişiklikler:")
    print(tabulate(table_data, headers=["Link", "Alan", "Eski Değer", "Yeni Değer"], tablefmt="fancy_grid"))
else:
    print("Ortak ürünlerde değişiklik bulunamadı.")

# -------------------------------
# Farkları CSV olarak kaydet
# -------------------------------
diff_rows = []
for comp in comparison:
    row = {"link": comp["link"]}
    for col, vals in comp['differences'].items():
        row[f"{col}_old"] = vals["old"]
        row[f"{col}_new"] = vals["new"]
    diff_rows.append(row)

df_diff = pd.DataFrame(diff_rows)
df_diff.to_csv("amazon_tablets_differences.csv", index=False, encoding="utf-8-sig")
print("\nFarklar CSV dosyası kaydedildi: amazon_tablets_differences.csv")
