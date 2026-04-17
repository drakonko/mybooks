import requests
from bs4 import BeautifulSoup
import re
import logging

def scrape_goodreads(url_or_isbn):
    """
    Извлича пълни метаданни от Goodreads за книга.
    Поддържа ISBN или директен URL.
    """
    session = requests.Session()
    # 2026 Headers - Goodreads е много капризен към User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }

    if "goodreads.com" in url_or_isbn:
        url = url_or_isbn
    else:
        # Търсене по ISBN/Заглавие
        url = f"https://www.goodreads.com/search?q={urllib.parse.quote(url_or_isbn)}" if "urllib" in globals() else f"https://www.goodreads.com/search?q={url_or_isbn}"

    try:
        response = session.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        # --- ЛОГИКА ЗА ТЪРСЕНЕ ---
        # Ако не сме на страницата на книгата (book/show), взимаме първия резултат
        if "book/show" not in response.url:
            soup = BeautifulSoup(response.content, "html.parser")
            first_link = soup.find("a", class_="bookTitle")
            if not first_link:
                return None
            book_url = "https://www.goodreads.com" + first_link['href']
            response = session.get(book_url, headers=headers, timeout=15)
            if response.status_code != 200:
                return None

        soup = BeautifulSoup(response.content, "html.parser")

        # 1. Заглавие (Title)
        title = soup.find("h1", {"data-testid": "bookTitle"})
        title = title.get_text(strip=True) if title else ""

        # 2. Автор (Author)
        author = soup.find("span", {"data-testid": "name"})
        author = author.get_text(strip=True) if author else ""

        # 3. Описание (Description)
        desc_div = soup.find("div", {"data-testid": "description"})
        description = desc_div.get_text(separator="\n", strip=True) if desc_div else ""
        # Махаме системните съобщения на Goodreads
        description = description.split("...more")[0].strip()

        # 4. Информация за Серия (Series Info)
        # Обикновено изглежда така: "The Stormlight Archive #1"
        series_tag = soup.find("h3", {"class": "Text__title3"}) # Сменено на h3 за новия дизайн
        series_full = series_tag.get_text(strip=True) if series_tag else ""
        
        # Опитваме се да разделим името на серията от номера (за твоята база)
        series_name = series_full
        if "#" in series_full:
            series_name = series_full.split("#")[0].strip()
            # Можеш да извлечеш и номера, ако искаш: series_num = series_full.split("#")[1].strip()

        # 5. Технически детайли (Pages, Year)
        details = soup.find("div", {"class": "FeaturedDetails"})
        details_text = details.get_text() if details else ""
        
        pages = re.search(r"(\d+)\s+pages", details_text)
        pages = pages.group(1) if pages else ""
        
        # Търсим годината - Goodreads ползва "First published" или просто "Published"
        year_match = re.search(r"(?:Published|published|First published)\s+.*(\d{4})", details_text)
        year = year_match.group(1) if year_match else ""

        # 6. Корица (Cover Image)
        cover_img = soup.find("img", {"class": "ResponsiveImage"})
        cover_url = cover_img['src'] if cover_img else ""

        return {
            "title": title,
            "author": author,
            "description": description,
            "series": series_name,
            "pages": pages,
            "year": year,
            "cover_url": cover_url
        }
    except Exception as e:
        print(f"Scraper Error: {e}")
        return None
