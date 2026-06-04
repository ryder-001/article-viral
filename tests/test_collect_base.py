import pytest
from scripts.collect.base import BaseCollector


class DummyCollector(BaseCollector):
    platform = "dummy"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        return [{"title": f"Article {keyword}", "url": "https://example.com/1"}]

    async def fetch_article(self, url: str) -> dict:
        return {"title": "Test", "content": "Content", "url": url}

    async def get_metrics(self, url: str) -> dict:
        return {"read_count": 200000, "like_count": 5000}


def test_is_viral_above_threshold():
    c = DummyCollector(viral_threshold=100000)
    assert c.is_viral({"read_count": 200000}) is True


def test_is_viral_below_threshold():
    c = DummyCollector(viral_threshold=100000)
    assert c.is_viral({"read_count": 5000}) is False


def test_platform_name():
    c = DummyCollector(viral_threshold=100000)
    assert c.platform == "dummy"
