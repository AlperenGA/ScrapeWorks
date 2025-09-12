import requests
from bs4 import BeautifulSoup
import pandas as pd

BASE_URL = "https://books.toscrape.com/"

def get_books_from_first_page():
    response = requests.get(BASE_URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    books = []

    for book in soup.select("article.product_pod"):
        title = book.h3.a['title']
        price = book.select_one(".price_color").text
        stock = book.select_one(".instock.availability").text.strip()
        rating = book.select_one("p.star-rating")['class'][-1]
        relative_url = book.h3.a['href']
        full_url = BASE_URL + relative_url

        books.append({
            'title': title,
            'price': price,
            'stock': stock,
            'rating': rating,
            'product_page_url': full_url
        })

    return books

if __name__ == "__main__":
    books = get_books_from_first_page()
    df = pd.DataFrame(books)
    df.to_csv("books_soup.csv", index=False, encoding='utf-8')
    df.to_excel("books_soup.xlsx", index=False)
    print(f"{len(books)} kitap başarıyla kaydedildi.")
