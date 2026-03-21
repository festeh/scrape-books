"""Scrape books from knigi-janzen.de search results."""

import argparse
import hashlib
import logging
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl, ValidationError

log = logging.getLogger(__name__)

BASE_URL = "https://www.knigi-janzen.de/"
SEARCH_URL = "https://www.knigi-janzen.de/result_search.php"
CACHE_DIR = Path("cache")
IMAGES_DIR = Path("images")
DB_PATH = Path("books.db")
DELAY = 0.5  # seconds between requests


class Book(BaseModel):
    gid: str
    code: str
    title: str
    author: str = ""
    binding: str = ""
    description: str = ""
    availability: str = ""
    price: str = ""
    discount: str = ""
    original_price: str = ""
    url: HttpUrl
    image_url: HttpUrl | None = None
    image_path: str = ""


_BOOK_COLUMNS = list(Book.model_fields.keys())
_BOOK_PLACEHOLDERS = ", ".join("?" for _ in _BOOK_COLUMNS)
_BOOK_COLUMNS_SQL = ", ".join(_BOOK_COLUMNS)


def init_db(db: Path) -> sqlite3.Connection:
    log.info("Initializing database at %s", db)
    conn = sqlite3.connect(db)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY,
            {", ".join(f"{c} TEXT" + (" UNIQUE" if c == "gid" else "") for c in _BOOK_COLUMNS)}
        )
    """)
    conn.commit()
    return conn


def cache_key(url: str, params: dict[str, str]) -> str:
    raw = url + str(sorted(params.items()))
    return hashlib.md5(raw.encode()).hexdigest()


def fetch_page(client: httpx.Client, page: int, search_params: dict[str, str], use_cache: bool) -> str:
    params = {**search_params, "pn": str(page)}
    key = cache_key(SEARCH_URL, params)
    cache_file = CACHE_DIR / f"{key}.html"

    if use_cache and cache_file.exists():
        log.debug("Page %d: using cached %s", page, cache_file)
        return cache_file.read_text(encoding="utf-8")

    log.info("Page %d: fetching from %s", page, SEARCH_URL)
    resp = client.get(SEARCH_URL, params=params)
    resp.raise_for_status()
    html = resp.text
    log.debug("Page %d: got %d bytes", page, len(html))

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(html, encoding="utf-8")
        log.debug("Page %d: cached to %s", page, cache_file)

    time.sleep(DELAY)
    return html


def get_total_pages(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    page_links = soup.select("a.page_num")
    if not page_links:
        return 1
    last_page = max(int(a.text) for a in page_links if a.text.strip().isdigit())
    return last_page


def _text_or(element: object, default: str = "") -> str:
    return element.text.strip() if element else default


def _find_text(table: object, pattern: str) -> str:
    node = table.find(string=re.compile(pattern))
    if not node:
        return ""
    parent = node.find_parent("div")
    return parent.get_text(strip=True) if parent else ""


def parse_books(html: str) -> list[Book]:
    soup = BeautifulSoup(html, "lxml")
    books: list[Book] = []

    for h2 in soup.select("h2.view_small_name"):
        link = h2.find("a")
        if not link:
            continue

        title = link.text.strip()
        href = link.get("href", "")

        gid_match = re.search(r"gid=(\d+)", href)
        gid = gid_match.group(1) if gid_match else ""

        table = h2.find_parent("table")
        if not table:
            log.warning("No parent table for book '%s', skipping", title)
            continue

        # Code
        code_node = table.find(string=re.compile(r"Код:\s*\d+"))
        code_match = re.search(r"Код:\s*(\d+)", code_node) if code_node else None
        code = code_match.group(1) if code_match else ""

        # Image
        img = table.find("img", src=re.compile(r"images/goods"))
        image_url = urljoin(BASE_URL, img["src"]) if img else None

        # Binding
        binding_node = table.find(string=re.compile(r"Переплет:"))
        binding = binding_node.strip().replace("Переплет: ", "") if binding_node else ""

        # Description
        desc_divs = table.find_all("div", style=re.compile(r"text-align:\s*justify"))
        description = desc_divs[0].get_text(strip=True) if desc_divs else ""

        # Availability
        availability = _find_text(table, r"Наличие:").removeprefix("Наличие:").strip()

        # Price
        price_div = table.find("div", style=re.compile(r"font-size:\s*30px"))

        try:
            book = Book(
                gid=gid,
                code=code,
                title=title,
                author=_text_or(table.find("h4", class_="view_small_author")),
                binding=binding,
                description=description,
                availability=availability,
                price=price_div.get_text(strip=True) if price_div else "",
                discount=_find_text(table, r"Скидка:"),
                original_price=_find_text(table, r"вместо:"),
                url=urljoin(BASE_URL, href),
                image_url=image_url,
            )
        except ValidationError as e:
            log.warning("Validation failed for book '%s' (gid=%s): %s", title, gid, e)
            continue

        log.debug("Parsed: [%s] %s — %s", book.gid, book.title, book.price)
        books.append(book)

    return books


def download_image(client: httpx.Client, url: str, use_cache: bool) -> str:
    if not url:
        return ""

    filename = url.split("/")[-1]
    dest = IMAGES_DIR / filename

    if use_cache and dest.exists():
        log.debug("Image %s: using cached", filename)
        return str(dest)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    log.debug("Image %s: downloading", filename)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        time.sleep(0.1)
    except httpx.HTTPError as e:
        log.error("Image %s: download failed: %s", filename, e)
        return ""

    return str(dest)


def save_book(conn: sqlite3.Connection, book: Book) -> None:
    values = tuple(str(v) if v is not None else "" for v in book.model_dump().values())
    conn.execute(
        f"INSERT OR REPLACE INTO books ({_BOOK_COLUMNS_SQL}) VALUES ({_BOOK_PLACEHOLDERS})",
        values,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape books from knigi-janzen.de")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached pages and images")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite database path")
    parser.add_argument("--search", default="картон", help="Search query")
    parser.add_argument("--cond", default="1,2", help="Condition filter")
    parser.add_argument("--no-images", action="store_true", help="Skip image downloads")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output (DEBUG level)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    use_cache = not args.no_cache
    search_params = {"gsearch": args.search, "cond": args.cond}

    log.info("Search: %r, cond: %s, cache: %s", args.search, args.cond, use_cache)

    conn = init_db(args.db)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (compatible; book-scraper/1.0)"},
        follow_redirects=True,
        timeout=30.0,
    )

    try:
        html = fetch_page(client, 1, search_params, use_cache)
        total_pages = get_total_pages(html)
        log.info("Found %d pages to scrape", total_pages)

        total_books = 0
        for page in range(1, total_pages + 1):
            if page > 1:
                html = fetch_page(client, page, search_params, use_cache)

            books = parse_books(html)
            log.info("Page %d/%d: %d books", page, total_pages, len(books))

            for book in books:
                if not args.no_images and book.image_url:
                    book = book.model_copy(update={"image_path": download_image(client, str(book.image_url), use_cache)})
                save_book(conn, book)

            conn.commit()
            total_books += len(books)

        total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        log.info("Done — scraped %d books this run, %d total in %s", total_books, total, args.db)

    finally:
        client.close()
        conn.close()


if __name__ == "__main__":
    main()
