"""百家号采集器 - 通过百度资讯搜索筛选百家号文章"""
import re
from bs4 import BeautifulSoup
from .base import BaseCollector


class BaijiahaoCollector(BaseCollector):
    platform = "baijiahao"
    # 百度资讯搜索（比普通搜索更适合找新闻/文章）
    SEARCH_URL = "https://www.baidu.com/s"

    def _parse_count(self, text: str) -> int:
        """解析数量文本"""
        if not text:
            return 0
        text = text.strip().replace(",", "").replace("+", "")
        try:
            if "万" in text:
                return int(float(text.replace("万", "")) * 10000)
            elif "亿" in text:
                return int(float(text.replace("亿", "")) * 100000000)
            return int(re.sub(r"[^\d]", "", text) or 0)
        except (ValueError, TypeError):
            return 0

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        """通过百度资讯搜索获取百家号文章

        使用 rtt=4 参数走资讯频道，结果中百家号文章占比更高。
        """
        results = []
        # 策略1：百度资讯搜索（rtt=4 资讯频道）
        params = {
            "wd": keyword,
            "rn": str(min(max_results, 50)),
            "rtt": "4",  # 资讯频道
            "vit": "osres",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }
        try:
            resp = await self._request(
                self.SEARCH_URL, params=params, headers=headers)
        except Exception:
            # fallback：普通搜索加百家号关键词
            try:
                params2 = {
                    "wd": f"{keyword} 百家号",
                    "rn": str(min(max_results, 50)),
                }
                resp = await self._request(
                    self.SEARCH_URL, params=params2, headers=headers)
            except Exception:
                return results

        soup = BeautifulSoup(resp.text, "lxml")
        # 百度搜索结果的选择器
        for item in soup.select(
                "div.result, div.result-op, div[class*='result']"):
            a = item.select_one("h3 a")
            if not a:
                continue
            title = a.get_text(strip=True)
            url = a.get("href", "")
            if not title or not url:
                continue
            # 提取来源/作者信息
            source_el = (
                item.select_one("span.c-color-gray") or
                item.select_one("a.c-color-gray") or
                item.select_one("span.c-gap-right-xsmall") or
                item.select_one("[class*='source']")
            )
            author = source_el.get_text(strip=True) if source_el else ""
            # 提取摘要
            abstract_el = (
                item.select_one("span.content-right_2s-H4") or
                item.select_one("div.c-abstract") or
                item.select_one("[class*='abstract']")
            )
            content = abstract_el.get_text(strip=True) if abstract_el else ""

            results.append({
                "title": title,
                "url": url,
                "content": content,
                "author": author,
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        """抓取百家号文章全文

        百度搜索结果的 URL 是跳转链接，需要先获取真实 URL。
        """
        try:
            # 百度搜索结果URL是302跳转
            resp = await self._request(url, follow_redirects=True)
            real_url = str(resp.url)
        except Exception:
            real_url = url
            try:
                resp = await self._request(url)
            except Exception:
                return {}

        soup = BeautifulSoup(resp.text, "lxml")
        # 百家号文章页面选择器（可能有多种布局）
        title = (
            soup.select_one("div.article-title h2") or
            soup.select_one("h1") or
            soup.select_one("[class*='title'] h1") or
            soup.select_one("[class*='article-title']")
        )
        content = (
            soup.select_one("div.article-content") or
            soup.select_one("article") or
            soup.select_one("[class*='article-content']") or
            soup.select_one("[id*='article']")
        )
        author_el = (
            soup.select_one("span.author-name") or
            soup.select_one("a.author-name") or
            soup.select_one("p.author-name") or
            soup.select_one("[class*='author'] span")
        )
        author_link = (
            soup.select_one("a.author-name") or
            soup.select_one("a[href*='author']") or
            soup.select_one("a.user-name")
        )
        # 提取指标
        read_count = 0
        like_count = 0
        comment_count = 0
        read_el = soup.select_one(
            "span.read-count, span.article-read-count, em.view-count, "
            "[class*='read'] span")
        like_el = soup.select_one(
            "span.like-count, span.praise-count, em.like-count, "
            "[class*='like'] span")
        comment_el = soup.select_one(
            "span.comment-count, em.comment-count, "
            "[class*='comment'] span")
        if read_el:
            read_count = self._parse_count(read_el.get_text())
        if like_el:
            like_count = self._parse_count(like_el.get_text())
        if comment_el:
            comment_count = self._parse_count(comment_el.get_text())
        # 从脚本中提取
        if not read_count:
            rc = re.search(r'"readCount"\s*:\s*(\d+)', resp.text)
            if rc:
                read_count = int(rc.group(1))
        if not like_count:
            lc = re.search(r'"likeCount"\s*:\s*(\d+)', resp.text)
            if lc:
                like_count = int(lc.group(1))

        author_url = ""
        if author_link:
            href = author_link.get("href", "")
            if href and not href.startswith("http"):
                author_url = "https://baijiahao.baidu.com" + href
            else:
                author_url = href
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": content.get_text(
                separator="\n", strip=True) if content else "",
            "author": author_el.get_text(strip=True) if author_el else "",
            "author_url": author_url,
            "publish_time": "",
            "url": real_url,
            "platform": self.platform,
            "read_count": read_count,
            "like_count": like_count,
            "comment_count": comment_count,
        }

    async def get_metrics(self, url: str) -> dict:
        """从文章页面提取阅读指标"""
        article = await self.fetch_article(url)
        return {
            "read_count": article.get("read_count", 0),
            "like_count": article.get("like_count", 0),
            "comment_count": article.get("comment_count", 0),
            "share_count": 0,
        }

    async def fetch_author_info(self, author_url: str) -> dict:
        """获取百家号作者信息"""
        if not author_url:
            return {}
        try:
            resp = await self._request(author_url)
            soup = BeautifulSoup(resp.text, "lxml")
            name_el = soup.select_one(
                "p.author-name, span.author-name, h1")
            desc_el = soup.select_one(
                "p.author-desc, span.author-intro, div.intro")
            avatar_el = soup.select_one("img.avatar, img.author-avatar")
            fan_el = soup.select_one(
                "span.fan-num, p.fans-num, span.subscribe-num")
            follower_count = 0
            if fan_el:
                follower_count = self._parse_count(fan_el.get_text())
            else:
                fan_match = re.search(
                    r'"fansCount"\s*:\s*(\d+)', resp.text)
                if fan_match:
                    follower_count = int(fan_match.group(1))
            article_count = 0
            art_el = soup.select_one("span.article-num, p.article-count")
            if art_el:
                article_count = self._parse_count(art_el.get_text())
            return {
                "name": name_el.get_text(strip=True) if name_el else "",
                "author_url": author_url,
                "avatar": avatar_el.get("src", "") if avatar_el else "",
                "description": desc_el.get_text(
                    strip=True) if desc_el else "",
                "follower_count": follower_count,
                "article_count": article_count,
                "total_read_count": 0,
                "level": "",
                "verified": False,
                "verified_info": "",
                "platform": self.platform,
            }
        except Exception:
            return {}
