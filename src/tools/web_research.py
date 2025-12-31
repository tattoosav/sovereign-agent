"""
Web Research Tool.

Enables the agent to search the web and fetch content for research.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A web search result."""
    title: str
    url: str
    snippet: str


class WebResearchTool(BaseTool):
    """Tool for web research - search and fetch web content."""

    name = "web_research"
    description = """Research information from the web.

Operations:
- search: Search the web using DuckDuckGo (no API key needed)
- fetch: Fetch and extract text content from a URL
- summarize: Fetch a URL and summarize key points

Use this to research APIs, documentation, solutions, tutorials, etc.
"""
    parameters = {
        "operation": "Operation: search, fetch, summarize",
        "query": "Search query (for search operation)",
        "url": "URL to fetch (for fetch/summarize operations)",
        "max_results": "Maximum search results (default: 5)",
    }

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

    def execute(
        self,
        operation: str,
        query: str = "",
        url: str = "",
        max_results: int = 5,
        **kwargs: Any
    ) -> ToolResult:
        """Execute web research operation."""
        try:
            if operation == "search":
                return self._search(query, max_results)
            elif operation == "fetch":
                return self._fetch(url)
            elif operation == "summarize":
                return self._summarize(url)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}. Use: search, fetch, summarize"
                )
        except httpx.TimeoutException:
            return ToolResult(success=False, output="", error="Request timed out")
        except httpx.RequestError as e:
            return ToolResult(success=False, output="", error=f"Request failed: {e}")
        except Exception as e:
            logger.exception(f"Web research error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _search(self, query: str, max_results: int) -> ToolResult:
        """Search the web using DuckDuckGo HTML."""
        if not query:
            return ToolResult(success=False, output="", error="Query is required")

        # Use DuckDuckGo HTML version (no API key needed)
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            response = self.client.get(search_url)
            response.raise_for_status()
            html = response.text

            # Parse results from HTML
            results = self._parse_ddg_results(html, max_results)

            if not results:
                return ToolResult(
                    success=True,
                    output=f"No results found for: {query}"
                )

            # Format results
            lines = [f"Search Results for: {query}", "=" * 50, ""]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r.title}")
                lines.append(f"   URL: {r.url}")
                lines.append(f"   {r.snippet}")
                lines.append("")

            return ToolResult(success=True, output="\n".join(lines))

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return ToolResult(success=False, output="", error=f"Search failed: {e}")

    def _parse_ddg_results(self, html: str, max_results: int) -> list[SearchResult]:
        """Parse DuckDuckGo HTML results."""
        results = []

        # Find result blocks
        # DuckDuckGo HTML structure: <a class="result__a" href="...">title</a>
        # and <a class="result__snippet">snippet</a>

        # Pattern for result links
        link_pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
        snippet_pattern = r'<a[^>]+class="result__snippet"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>)*[^<]*)</a>'

        links = re.findall(link_pattern, html)
        snippets = re.findall(snippet_pattern, html)

        for i, (url, title) in enumerate(links[:max_results]):
            snippet = snippets[i] if i < len(snippets) else ""
            # Clean snippet of HTML tags
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()

            # DuckDuckGo uses redirect URLs, extract actual URL
            if "uddg=" in url:
                actual_url = re.search(r'uddg=([^&]+)', url)
                if actual_url:
                    from urllib.parse import unquote
                    url = unquote(actual_url.group(1))

            results.append(SearchResult(
                title=title.strip(),
                url=url,
                snippet=snippet[:200] + "..." if len(snippet) > 200 else snippet
            ))

        return results

    def _fetch(self, url: str) -> ToolResult:
        """Fetch and extract text content from a URL."""
        if not url:
            return ToolResult(success=False, output="", error="URL is required")

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = "https://" + url
        except Exception:
            return ToolResult(success=False, output="", error="Invalid URL")

        try:
            response = self.client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type:
                text = self._extract_text_from_html(response.text)
            elif "text/plain" in content_type:
                text = response.text
            elif "application/json" in content_type:
                text = response.text
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unsupported content type: {content_type}"
                )

            # Truncate if too long
            if len(text) > 15000:
                text = text[:15000] + "\n\n[Content truncated...]"

            lines = [
                f"Content from: {url}",
                "=" * 50,
                "",
                text
            ]

            return ToolResult(success=True, output="\n".join(lines))

        except httpx.HTTPStatusError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
            )

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from HTML."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Convert some tags to text
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?p[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?div[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?h[1-6][^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<li[^>]*>', '\n• ', html, flags=re.IGNORECASE)

        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', html)

        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")

        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = '\n'.join(line.strip() for line in text.splitlines())
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _summarize(self, url: str) -> ToolResult:
        """Fetch URL and provide a summary."""
        # First fetch the content
        fetch_result = self._fetch(url)
        if not fetch_result.success:
            return fetch_result

        # Extract key points (simple extraction)
        content = fetch_result.output
        lines = content.split('\n')

        # Get title and first substantial paragraphs
        summary_lines = ["Summary:", "=" * 50, ""]

        paragraphs = []
        current_para = []

        for line in lines[3:]:  # Skip header
            line = line.strip()
            if line:
                current_para.append(line)
            elif current_para:
                para_text = ' '.join(current_para)
                if len(para_text) > 50:  # Substantial paragraph
                    paragraphs.append(para_text)
                current_para = []

        # Take first 5 substantial paragraphs
        for i, para in enumerate(paragraphs[:5], 1):
            if len(para) > 300:
                para = para[:300] + "..."
            summary_lines.append(f"{i}. {para}")
            summary_lines.append("")

        if not paragraphs:
            summary_lines.append("Could not extract summary from page.")

        return ToolResult(success=True, output="\n".join(summary_lines))

    def __del__(self):
        """Cleanup HTTP client."""
        try:
            self.client.close()
        except Exception:
            pass
