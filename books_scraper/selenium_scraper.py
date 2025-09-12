from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import pandas as pd

def get_books_with_selenium():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')

    service = Service()  # chromedriver path ayarlanabilir, sistemde varsa boş bırakılabilir
    driver = webdriver.Chrome(service=service, options=options)

    driver.get("https://books.toscrape.com/")
    time.sleep(2)

    books = []
    book_elements = driver.find_elements(By.CSS_SELECTOR, "article.product_pod")
    for book in book_elements:
        title = book.find_element(By.CSS_SELECTOR, "h3 a").get_attribute("title")
        price = book.find_element(By.CSS_SELECTOR, ".price_color").text
        stock = book.find_element(By.CSS_SELECTOR, ".instock.availability").text.strip()
        rating_class = book.find_element(By.CSS_SELECTOR, "p.star-rating").get_attribute("class")
        rating = rating_class.split()[-1]
        relative_url = book.find_element(By.CSS_SELECTOR, "h3 a").get_attribute("href")

        books.append({
            'title': title,
            'price': price,
            'stock': stock,
            'rating': rating,
            'product_page_url': relative_url
        })

    driver.quit()
    return books

def save_books_to_files(data, csv_path, excel_path):
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False, encoding='utf-8')
    df.to_excel(excel_path, index=False)
    print(f"{len(data)} kitap başarıyla kaydedildi.")
    print(f"- CSV: {csv_path}")
    print(f"- Excel: {excel_path}")

if __name__ == "__main__":
    books = get_books_with_selenium()
    save_books_to_files(books, "books_selenium.csv", "books_selenium.xlsx")
