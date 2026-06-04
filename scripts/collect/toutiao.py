"""今日头条采集器 - 通过头条搜索获取文章"""
import re
import json
from urllib.parse import unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from .base import BaseCollector


class ToutiaoCollector(BaseCollector):
    platform = "toutiao"
    SEARCH_URL = "https://so.toutiao.com/search"

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

    def _extract_article_url(self, raw_url: str) -> str:
        """从头条跳转链接中提取真正的文章 URL"""
        from urllib.parse import unquote
        # 多层解码
        decoded = unquote(unquote(unquote(raw_url)))
        group_id = None
        # 模式1: group/xxx/ 在解码后的 URL 中
        m = re.search(r'group/(\d{10,})', decoded)
        if m:
            group_id = m.group(1)
        # 模式2: groupid=xxx
        if not group_id:
            m = re.search(r'groupid=(\d{10,})', decoded)
            if m:
                group_id = m.group(1)
        # 模式3: group_id 或 item_id
        if not group_id:
            m = re.search(r'(?:group_id|item_id)=(\d{10,})', decoded)
            if m:
                group_id = m.group(1)
        # 模式4: search_result_id
        if not group_id:
            m = re.search(r'search_result_id["\s:]*(\d{10,})', decoded)
            if m:
                group_id = m.group(1)
        if group_id:
            return f"https://www.toutiao.com/article/{group_id}/"
        # 如果是正常 URL 直接返回
        if raw_url.startswith("http") and "toutiao.com" in raw_url:
            return raw_url
        return ""

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        params = {
            "keyword": keyword, "pd": "information",
            "source": "search_subtab_switch"
        }
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.result-content"):
            a = item.select_one("a")
            if not a:
                continue
            raw_url = a.get("href", "")
            article_url = self._extract_article_url(raw_url)
            if not article_url:
                continue
            author_el = item.select_one("span.source, span.media-name")
            results.append({
                "title": a.get_text(strip=True),
                "url": article_url,
                "author": author_el.get_text(
                    strip=True) if author_el else "",
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        try:
            resp = await self._request(url)
        except Exception:
            return {}
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.select_one("h1") or soup.select_one("title")
        article = (soup.select_one("article")
                   or soup.select_one(".article-content"))
        author_el = soup.select_one(
            "span.article-sub a, span.name a, a.author-name")
        read_count = 0
        like_count = 0
        comment_count = 0
        # 从页面 JSON 提取指标
        for script in soup.select("script"):
            text = script.get_text()
            if "readCount" in text or "read_count" in text:
                rc = re.search(r'"readCount"\s*:\s*(\d+)', text)
                lc = re.search(r'"diggCount"\s*:\s*(\d+)', text)
                cc = re.search(r'"commentCount"\s*:\s*(\d+)', text)
                if not rc:
                    rc = re.search(r'"read_count"\s*:\s*(\d+)', text)
                if not lc:
                    lc = re.search(r'"digg_count"\s*:\s*(\d+)', text)
                if not cc:
                    cc = re.search(r'"comment_count"\s*:\s*(\d+)', text)
                if rc:
                    read_count = int(rc.group(1))
                if lc:
                    like_count = int(lc.group(1))
                if cc:
                    comment_count = int(cc.group(1))
                break
        author_name = ""
        author_url = ""
        if author_el:
            author_name = author_el.get_text(strip=True)
            href = author_el.get("href", "")
            if href and not href.startswith("http"):
                author_url = "https://www.toutiao.com" + href
            else:
                author_url = href
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": article.get_text(
                separator="\n", strip=True) if article else "",
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
        article = await self.fetch_article(url)
        return {
            "read_count": article.get("read_count", 0),
            "like_count": article.get("like_count", 0),
            "comment_count": article.get("comment_count", 0),
            "share_count": 0,
        }

    async def fetch_author_info(self, author_url: str) -> dict:
        if not author_url:
            return {}
        try:
            resp = await self._request(author_url)
            soup = BeautifulSoup(resp.text, "lxml")
            name_el = soup.select_one(
                "span.name, h1.user-name, div.author-name")
            desc_el = soup.select_one(
                "span.desc, p.user-desc, div.author-desc")
            avatar_el = soup.select_one("img.avatar, img.user-avatar")
            follower_count = 0
            fan_match = re.search(
                r'"followerCount"\s*:\s*(\d+)', resp.text)
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
