"""搜狐采集器 - 通过搜狐搜索获取文章"""
import re
from bs4 import BeautifulSoup
from .base import BaseCollector


class SohuCollector(BaseCollector):
    platform = "sohu"
    SEARCH_URL = "https://search.sohu.com/"

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
            m = re.search(r"\d+", text)
            return int(m.group(0)) if m else 0
        except (ValueError, TypeError):
            return 0

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        params = {"keyword": keyword, "type": "news"}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.news-list li, div.result-item"):
            a = item.select_one("a")
            if not a:
                continue
            url = a.get("href", "")
            if url and not url.startswith("http"):
                url = "https:" + url
            author_el = item.select_one("span.source, p.source")
            results.append({
                "title": a.get_text(strip=True),
                "url": url,
                "author": author_el.get_text(
                    strip=True) if author_el else "",
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        """抓取搜狐文章并提取指标"""
        try:
            resp = await self._request(url)
        except Exception:
            return {}
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.select_one("h1") or soup.select_one("title")
        content = soup.select_one("article") or soup.select_one("div.article")
        author_el = soup.select_one(
            "span.user-info a, a.author-name, span.name")
        # 搜狐文章页可能有阅读量
        read_count = 0
        like_count = 0
        comment_count = 0
        read_el = soup.select_one("span.read-num, em.num")
        if read_el:
            read_count = self._parse_count(read_el.get_text())
        # 从内嵌数据提取
        rc = re.search(r'"readNum"\s*:\s*(\d+)', resp.text)
        lc = re.search(r'"praiseNum"\s*:\s*(\d+)', resp.text)
        cc = re.search(r'"commentNum"\s*:\s*(\d+)', resp.text)
        if rc:
            read_count = max(read_count, int(rc.group(1)))
        if lc:
            like_count = int(lc.group(1))
        if cc:
            comment_count = int(cc.group(1))
        author_name = ""
        author_url = ""
        if author_el:
            author_name = author_el.get_text(strip=True)
            href = author_el.get("href", "")
            if href and not href.startswith("http"):
                author_url = "https://www.sohu.com" + href
            else:
                author_url = href
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": content.get_text(
                separator="\n", strip=True) if content else "",
            "author": author_name,
            "author_url": author_url,
            "publish_time": "",
            "url": url,
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
        """获取搜狐号作者信息"""
        if not author_url:
            return {}
        try:
            resp = await self._request(author_url)
            soup = BeautifulSoup(resp.text, "lxml")
            name_el = soup.select_one("h1, span.name, p.author-name")
            desc_el = soup.select_one("p.desc, span.intro")
            avatar_el = soup.select_one("img.avatar")
            follower_count = 0
            fan_match = re.search(
                r'"fansCount"\s*:\s*(\d+)', resp.text)
            if fan_match:
                follower_count = int(fan_match.group(1))
            return {
                "name": name_el.get_text(strip=True) if name_el else "",
                "author_url": author_url,
                "avatar": avatar_el.get("src", "") if avatar_el else "",
                "description": desc_el.get_text(
                    strip=True) if desc_el else "",
                "follower_count": follower_count,
                "article_count": 0,
                "total_read_count": 0,
                "level": "",
                "verified": False,
                "verified_info": "",
                "platform": self.platform,
            }
        except Exception:
            return {}

