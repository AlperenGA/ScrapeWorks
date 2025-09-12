import scrapy
import pandas as pd

class BooksSpider(scrapy.Spider):
    name = "books"
    start_urls = ["https://books.toscrape.com/"]

    def __init__(self):
        super().__init__()
        self.books = []

    def parse(self, response):
        for book in response.css("article.product_pod"):
            item = {
                'title': book.css("h3 a::attr(title)").get(),
                'price': book.css(".price_color::text").get(),
                'stock': book.css(".instock.availability::text").re_first(r'\S+'),
                'rating': book.css("p.star-rating").attrib.get('class').split()[-1],
                'product_page_url': response.urljoin(book.css("h3 a::attr(href)").get())
            }
            self.books.append(item)

        next_page = response.css('li.next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)
        else:
            df = pd.DataFrame(self.books)
            df.to_csv('books.csv', index=False, encoding='utf-8')
            df.to_excel('books.xlsx', index=False)
            self.log(f"{len(self.books)} kitap kaydedildi.")
