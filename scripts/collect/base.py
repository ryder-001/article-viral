"""采集器基类，定义接口和通用逻辑"""
import asyncio
import random
import httpx
from abc import ABC, abstractmethod

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


class BaseCollector(ABC):
    platform: str = ""

    def __init__(self, viral_threshold: int = 100000, delay: tuple = (2, 5),
                 user_agents: list = None, proxy: str = ""):
        self.viral_threshold = viral_threshold
        self.delay = delay
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.proxy = proxy or None

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    async def _request(self, url: str, **kwargs) -> httpx.Response:
        await asyncio.sleep(random.uniform(*self.delay))
        async with httpx.AsyncClient(
            proxy=self.proxy, timeout=30, follow_redirects=True
        ) as client:
            response = await client.get(url, headers=self._get_headers(), **kwargs)
            response.raise_for_status()
            return response

    def is_viral(self, metrics: dict) -> bool:
        read_count = metrics.get("read_count", 0) or 0
        like_count = metrics.get("like_count", 0) or 0
        comment_count = metrics.get("comment_count", 0) or 0
        share_count = metrics.get("share_count", 0) or 0
        total_engagement = like_count + comment_count + share_count
        return (read_count >= self.viral_threshold
                or total_engagement >= (self.viral_threshold // 10))

    @abstractmethod
    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        """搜索文章列表，返回 [{title, url, ...}]"""
        pass

    @abstractmethod
    async def fetch_article(self, url: str) -> dict:
        """抓取文章全文，返回 {title, content, author, publish_time, ...}"""
        pass

    @abstractmethod
    async def get_metrics(self, url: str) -> dict:
        """获取文章指标，返回 {read_count, like_count, comment_count, share_count}"""
        pass

    async def fetch_author_info(self, author_url: str) -> dict:
        """获取作者详细信息，返回 {name, author_url, avatar, description,
        follower_count, article_count, total_read_count, level, verified, verified_info}
        子类可覆盖此方法实现平台特定解析"""
        return {}
