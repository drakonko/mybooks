import requests
from bs4 import BeautifulSoup
import logging
import re

def fetch_bibliography_from_bn(author_name):
    slug = author_name.lower().strip().replace(" ", "-").replace(".", "")
    url = f"https://booknotification.com/authors/{slug}/"
    logging.info(f"DEBUG: Scraper URL: {url}")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return []

        soup = BeautifulSoup(response.content, 'html.parser')
        works = []
        series_headers = soup.find_all('h3', class_='series_title')

        for header in series_headers:
            series_name = header.get_text().strip().replace("List of ", "").replace(" Books in Publication Order", "")
            container = header.find_next('div', class_='table-responsive')
            if not container: continue
            
            table = container.find('table')
            if not table: continue

            rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    order = cols[0].get_text(strip=True)
                    title_div = cols[2].find('div', class_='titles')
                    if not title_div: continue
                    title = re.sub(r'^\d+\.?\d*\s*', '', title_div.get_text(strip=True)).strip()
                    year_td = row.find('td', class_='text-center')
                    year = year_td.get_text(strip=True) if year_td else ""
                    works.append((author_name, series_name, title, order, year, ""))
        return works
    except Exception as e:
        logging.error(f"Scraper Error: {e}")
        return []
