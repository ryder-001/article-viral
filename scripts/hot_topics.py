"""各平台热榜采集模块

浏览器采集知乎热榜、微博热搜、头条热榜、百度热搜，返回结构化热点数据。
复用 browser_fetcher.py 的 Playwright 基础设施。
"""
import asyncio
from datetime import datetime
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page
from scripts.login_manager import load_cookies_to_context, has_valid_cookies


class HotTopicsFetcher:
    """各平台热榜采集器"""

    def __init__(self, headless: bool = True, timeout: int = 20000):
        self.headless = headless
        self.timeout = timeout
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless
        )

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _new_page(self, platform: str = "") -> Page:
        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        if platform and has_valid_cookies(platform):
            await load_cookies_to_context(context, platform)
        page = await context.new_page()
        page.set_default_timeout(self.timeout)
        return page

    async def fetch_all(self, platforms: list[str] = None) -> dict:
        """采集所有平台热榜，返回 {platform: [topics]}"""
        if platforms is None:
            platforms = ["zhihu", "weibo", "toutiao", "baidu"]
        results = {}
        for platform in platforms:
            method = getattr(self, f"_fetch_{platform}", None)
            if method:
                try:
                    topics = await method()
                    results[platform] = topics
                except Exception as e:
                    results[platform] = {"error": str(e)}
        return results

    async def _fetch_zhihu(self) -> list[dict]:
        """知乎热榜"""
        page = await self._new_page("zhihu")
        topics = []
        try:
            await page.goto("https://www.zhihu.com/hot", wait_until="domcontentloaded")
            await page.wait_for_selector(".HotList-item", timeout=10000)
            items = await page.query_selector_all(".HotList-item")
            for item in items[:30]:
                title_el = await item.query_selector(".HotList-itemTitle")
                metric_el = await item.query_selector(".HotList-itemMetrics")
                title = await title_el.inner_text() if title_el else ""
                metric = await metric_el.inner_text() if metric_el else ""
                link_el = await item.query_selector("a")
                url = await link_el.get_attribute("href") if link_el else ""
                if url and not url.startswith("http"):
                    url = "https://www.zhihu.com" + url
                if title:
                    topics.append({
                        "title": title.strip(),
                        "heat": metric.strip(),
                        "url": url,
                        "platform": "zhihu",
                    })
        finally:
            await page.context.close()
        return topics

    async def _fetch_weibo(self) -> list[dict]:
        """微博热搜"""
        page = await self._new_page("weibo")
        topics = []
        try:
            await page.goto("https://s.weibo.com/top/summary", wait_until="domcontentloaded")
            await page.wait_for_selector("#pl_top_realtimehot table tr", timeout=10000)
            rows = await page.query_selector_all("#pl_top_realtimehot table tr")
            for row in rows[1:51]:  # 跳过表头，取前50
                td_els = await row.query_selector_all("td")
                if len(td_els) < 2:
                    continue
                link_el = await td_els[1].query_selector("a")
                span_el = await td_els[1].query_selector("span")
                title = await link_el.inner_text() if link_el else ""
                heat = await span_el.inner_text() if span_el else ""
                href = await link_el.get_attribute("href") if link_el else ""
                if href and not href.startswith("http"):
                    href = "https://s.weibo.com" + href
                if title:
                    topics.append({
                        "title": title.strip(),
                        "heat": heat.strip(),
                        "url": href,
                        "platform": "weibo",
                    })
        finally:
            await page.context.close()
        return topics

    async def _fetch_toutiao(self) -> list[dict]:
        """今日头条热榜"""
        page = await self._new_page("toutiao")
        topics = []
        try:
            await page.goto("https://www.toutiao.com/hot-event/hot-board/",
                            wait_until="domcontentloaded")
            await page.wait_for_selector("[class*='hot-list'] a, .hot-item",
                                         timeout=10000)
            # 头条热榜结构可能变化，尝试多种选择器
            items = await page.query_selector_all("[class*='title']")
            if not items:
                items = await page.query_selector_all(".hot-item")
            links = await page.query_selector_all("[class*='hot-list'] a, a[href*='/trending/']")
            for link in links[:30]:
                title = await link.inner_text()
                href = await link.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = "https://www.toutiao.com" + href
                title = title.strip()
                if title and len(title) > 2:
                    topics.append({
                        "title": title,
                        "heat": "",
                        "url": href,
                        "platform": "toutiao",
                    })
        finally:
            await page.context.close()
        return topics

    async def _fetch_baidu(self) -> list[dict]:
        """百度热搜"""
        page = await self._new_page()
        topics = []
        try:
            await page.goto("https://top.baidu.com/board?tab=realtime",
                            wait_until="domcontentloaded")
            await page.wait_for_selector(".c-single-text-ellipsis",
                                         timeout=10000)
            items = await page.query_selector_all(
                ".category-wrap_iQLoo .content_1YWBm")
            for item in items[:30]:
                title_el = await item.query_selector(".c-single-text-ellipsis")
                metric_el = await item.query_selector(".hot-index_1Bl1a")
                title = await title_el.inner_text() if title_el else ""
                heat = await metric_el.inner_text() if metric_el else ""
                # 百度热搜的链接
                parent = await item.query_selector("a")
                href = await parent.get_attribute("href") if parent else ""
                if title:
                    topics.append({
                        "title": title.strip(),
                        "heat": heat.strip(),
                        "url": href or "",
                        "platform": "baidu",
                    })
        finally:
            await page.context.close()
        return topics


async def fetch_hot_topics(platforms: list[str] = None,
                           headless: bool = True) -> dict:
    """便捷函数：采集热榜并返回结果"""
    fetcher = HotTopicsFetcher(headless=headless)
    await fetcher.start()
    try:
        results = await fetcher.fetch_all(platforms)
    finally:
        await fetcher.close()
    results["_meta"] = {
        "fetch_time": datetime.now().isoformat(),
        "platforms": platforms or ["zhihu", "weibo", "toutiao", "baidu"],
    }
    return results
