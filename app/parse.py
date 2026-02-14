from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class Quote:
    text: str
    author: str
    tags: list[str]


BASE_URL = "https://quotes.toscrape.com"


def _get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    re = session.get(url, timeout=20)
    re.raise_for_status()
    return BeautifulSoup(re.text, "html.parser")


def _parse_quotes_and_author_links(soup: BeautifulSoup) \
        -> (list)[tuple[Quote, Optional[str]]]:
    result: list[tuple[Quote, Optional[str]]] = []

    for block in soup.select(".quote"):
        text_el = block.select_one(".text")
        author_el = block.select_one(".author")
        tags_el = block.select(".tags .tag")

        if not text_el or not author_el:
            continue

        quote = Quote(
            text=text_el.get_text(strip=True),
            author=author_el.get_text(strip=True),
            tags=[t.get_text(strip=True) for t in tags_el],
        )

        author_link_el = block.select_one("span > a[href^='/author/']")
        href = author_link_el.get("href") if author_link_el else None
        author_url = (BASE_URL + href) if href else None

        result.append((quote, author_url))

    return result


def _get_next_page_url(soup: BeautifulSoup) -> Optional[str]:
    next_link = soup.select_one("li.next > a")
    href = next_link.get("href") if next_link else None
    return (BASE_URL + href) if href else None


def _parse_author_bio(session: requests.Session, author_url: str) -> dict:
    soup = _get_soup(session, author_url)

    name = soup.select_one("h3.author-title")
    born_date = soup.select_one("span.author-born-date")
    born_location = soup.select_one("span.author-born-location")
    description = soup.select_one("div.author-description")

    return {
        "name": name.get_text(strip=True) if name else "",
        "born_date": born_date.get_text(strip=True) if born_date else "",
        "born_location": born_location.get_text(strip=True)
        if born_location else "",
        "description": description.get_text(strip=True) if description else "",
        "url": author_url,
    }


def main(output_csv_path: str) -> None:
    quotes_csv_path = output_csv_path

    authors_csv_path = output_csv_path.replace(".csv", "_authors.csv")
    collect_authors_bio = True

    delay_sec = 0.3

    authors_cache: Dict[str, dict] = {}

    with requests.Session() as session:
        with open(quotes_csv_path, "w", newline="",
                  encoding="utf-8") as f_quotes:
            quotes_writer = csv.DictWriter(f_quotes,
                                           fieldnames=["text", "author",
                                                       "tags"])
            quotes_writer.writeheader()

            if collect_authors_bio:
                f_authors = open(authors_csv_path, "w", newline="",
                                 encoding="utf-8")
                authors_writer = csv.DictWriter(
                    f_authors,
                    fieldnames=["name", "born_date", "born_location",
                                "description", "url"],
                )
                authors_writer.writeheader()
            else:
                f_authors = None
                authors_writer = None

            try:
                url: Optional[str] = BASE_URL

                while url:
                    soup = _get_soup(session, url)
                    items = _parse_quotes_and_author_links(soup)

                    for quote, author_url in items:
                        quotes_writer.writerow(
                            {
                                "text": quote.text,
                                "author": quote.author,
                                "tags": ", ".join(quote.tags),
                            }
                        )

                        if authors_writer is not None and author_url:
                            if author_url not in authors_cache:
                                bio = _parse_author_bio(session, author_url)
                                authors_cache[author_url] = bio
                                authors_writer.writerow(bio)
                                time.sleep(delay_sec)

                    url = _get_next_page_url(soup)
                    if url:
                        time.sleep(delay_sec)

            finally:
                if f_authors is not None:
                    f_authors.close()

    if collect_authors_bio:
        print(f"Saved quotes to: {quotes_csv_path}")
        print(
            f"Saved authors to: {authors_csv_path} "
            f"(unique authors: {len(authors_cache)})")
    else:
        print(f"Saved quotes to: {quotes_csv_path}")


if __name__ == "__main__":
    main("quotes.csv")
