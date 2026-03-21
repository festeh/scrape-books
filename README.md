# scrape-books

Scrape books from [knigi-janzen.de](https://www.knigi-janzen.de/) search results into SQLite.

## Setup

```
uv sync
```

## Usage

```
uv run python -m scrape_books.scraper
```

This scrapes all pages for the default search query (`картон`, condition `1,2`), saves book data to `books.db`, and downloads cover images to `images/`.

Pages are cached to `cache/` by default — re-runs skip already fetched pages.

### Options

```
--search QUERY    Search query (default: картон)
--cond COND       Condition filter (default: 1,2)
--db PATH         SQLite database path (default: books.db)
--no-cache        Ignore cached pages and images, re-fetch everything
--no-images       Skip image downloads
-v, --verbose     Show DEBUG-level logs
```

### Examples

```
# Different search query
uv run python -m scrape_books.scraper --search "сказки" --cond 2

# Re-fetch everything, skip images
uv run python -m scrape_books.scraper --no-cache --no-images

# Verbose output
uv run python -m scrape_books.scraper -v
```

## Output

### SQLite schema (`books.db`)

| Column         | Description              |
|----------------|--------------------------|
| gid            | Product ID               |
| code           | Product code             |
| title          | Book title               |
| author         | Author                   |
| binding        | Binding type (переплет)  |
| description    | Short description        |
| availability   | Stock/shipping status    |
| price          | Current price            |
| discount       | Discount percentage      |
| original_price | Price before discount    |
| url            | Book page URL            |
| image_url      | Cover image URL          |
| image_path     | Local path to saved image|

### Images

Cover images are saved to `images/` using the original filename from the site.
