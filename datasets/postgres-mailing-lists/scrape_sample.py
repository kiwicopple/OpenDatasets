#!/usr/bin/env python3
"""
Quick sample scrape to see the data format.

Usage:
    export FIRECRAWL_API_KEY=your_key
    python scrape_sample.py
"""

import os
import json
from firecrawl import FirecrawlApp

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")

def main():
    if not FIRECRAWL_API_KEY:
        print("Error: Set FIRECRAWL_API_KEY environment variable")
        return

    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

    # Scrape a single page to see the format
    print("Scraping pgsql-hackers list page...")
    result = app.scrape_url(
        "https://www.postgresql.org/list/pgsql-hackers/",
        params={
            'formats': ['markdown', 'html', 'links']
        }
    )

    # Save result
    with open('sample_scrape.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)

    print("Saved to sample_scrape.json")

    # Print summary
    print("\n--- Metadata ---")
    print(json.dumps(result.get('metadata', {}), indent=2))

    print("\n--- Links found ---")
    links = result.get('links', [])
    for link in links[:20]:
        print(f"  {link}")

    print(f"\n... and {len(links) - 20} more links" if len(links) > 20 else "")

    print("\n--- Content preview (first 2000 chars) ---")
    print(result.get('markdown', '')[:2000])


if __name__ == "__main__":
    main()
