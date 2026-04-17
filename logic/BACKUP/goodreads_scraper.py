import requests
from bs4 import BeautifulSoup
import re

def scrape_goodreads(url_or_isbn):
    """
    Crawls a Goodreads book page to extract full metadata.
    """
    # If it's an ISBN, we search first. If it's a URL, we go direct.
    if "goodreads.com" in url_or_isbn:
        url = url_or_isbn
    else:
        url = f"https://www.goodreads.com/search?q={url_or_isbn}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, "lxml")

        # 1. Title
        title = soup.find("h1", {"data-testid": "bookTitle"})
        title = title.get_text(strip=True) if title else ""

        # 2. Author
        author = soup.find("span", {"data-testid": "name"})
        author = author.get_text(strip=True) if author else ""

        # 3. Description (Syncing synposis)
        desc_div = soup.find("div", {"data-testid": "description"})
        description = desc_div.get_text(separator="\n", strip=True) if desc_div else ""
        # Remove "show more" text if present
        description = description.replace("...more", "").strip()

        # 4. Series Info
        series = soup.find("h2", {"class": "Text__title3"})
        series_text = series.get_text(strip=True) if series else ""

        # 5. Technical Details (Pages, Year)
        # Goodreads hides these in a "FeaturedDetails" section
        details = soup.find("div", {"class": "FeaturedDetails"})
        details_text = details.get_text() if details else ""
        
        pages = re.search(r"(\d+)\s+pages", details_text)
        pages = pages.group(1) if pages else ""
        
        year = re.search(r"First published\s+(.*?\d{4})", details_text)
        year = year.group(1)[-4:] if year else ""

        # 6. Cover Image
        cover_img = soup.find("img", {"class": "ResponsiveImage"})
        cover_url = cover_img['src'] if cover_img else ""

        return {
            "title": title,
            "author": author,
            "description": description,
            "series": series_text,
            "pages": pages,
            "year": year,
            "cover_url": cover_url
        }
    except Exception as e:
        print(f"Scraper Error: {e}")
        return None