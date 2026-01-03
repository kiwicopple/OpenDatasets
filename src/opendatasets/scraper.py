"""
Web scraping utilities for OpenDatasets.

Supports:
- Simple HTTP scraping with requests/BeautifulSoup
- Rate limiting and polite crawling
- Content extraction and cleaning
"""

import time
from dataclasses import dataclass, field
from typing import Iterator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel


class ScrapedPage(BaseModel):
    """A scraped web page."""

    url: str
    title: str | None = None
    content: str  # Main text content
    html: str | None = None  # Raw HTML (optional)
    links: list[str] = []
    metadata: dict = {}


@dataclass
class Scraper:
    """
    Web scraper with rate limiting and content extraction.

    Example:
        scraper = Scraper(base_url="https://example.com")
        for page in scraper.crawl("/docs/", max_pages=100):
            print(page.title, len(page.content))
    """

    base_url: str
    delay: float = 1.0  # Seconds between requests
    timeout: int = 30
    max_retries: int = 3
    headers: dict = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    def __post_init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._last_request_time = 0

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def fetch(self, url: str) -> requests.Response:
        """Fetch a URL with retries and rate limiting."""
        full_url = urljoin(self.base_url, url)
        self._wait_for_rate_limit()

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(full_url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff

    def scrape(self, url: str, extract_links: bool = True) -> ScrapedPage:
        """Scrape a single page and extract content."""
        response = self.fetch(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Extract title
        title = None
        if soup.title:
            title = soup.title.get_text(strip=True)
        elif soup.h1:
            title = soup.h1.get_text(strip=True)

        # Extract main content
        main = soup.find("main") or soup.find("article") or soup.find("body")
        content = main.get_text(separator="\n", strip=True) if main else ""

        # Extract links
        links = []
        if extract_links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/") or href.startswith(self.base_url):
                    links.append(urljoin(self.base_url, href))

        return ScrapedPage(
            url=urljoin(self.base_url, url),
            title=title,
            content=content,
            html=response.text,
            links=links,
            metadata={
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
            },
        )

    def crawl(
        self,
        start_url: str,
        max_pages: int = 100,
        url_filter: callable = None,
    ) -> Iterator[ScrapedPage]:
        """
        Crawl pages starting from a URL.

        Args:
            start_url: Starting URL path
            max_pages: Maximum pages to crawl
            url_filter: Optional function to filter URLs (return True to include)

        Yields:
            ScrapedPage objects
        """
        visited = set()
        queue = [start_url]

        while queue and len(visited) < max_pages:
            url = queue.pop(0)

            # Normalize URL
            parsed = urlparse(url)
            normalized = parsed.path + (f"?{parsed.query}" if parsed.query else "")

            if normalized in visited:
                continue

            visited.add(normalized)

            try:
                page = self.scrape(url)
                yield page

                # Add new links to queue
                for link in page.links:
                    link_parsed = urlparse(link)
                    link_normalized = link_parsed.path

                    if link_normalized not in visited:
                        if url_filter is None or url_filter(link):
                            queue.append(link)

            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue


def scrape_page(url: str, **kwargs) -> ScrapedPage:
    """Convenience function to scrape a single page."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    scraper = Scraper(base_url=base_url, **kwargs)
    return scraper.scrape(parsed.path)
