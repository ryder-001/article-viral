"""微博采集器 - 通过微博搜索获取热门微博"""
import re
from bs4 import BeautifulSoup
from .base import BaseCollector


class WeiboCollector(BaseCollector):
    platform = "weibo"
    SEARCH_URL = "https://s.weibo.com/weibo"

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
        params = {"q": keyword, "xsort": "hot", "suball": "1"}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.select("div.card-wrap"):
            content = card.select_one("p.txt")
            link = card.select_one("a[action-type='feed_list_url']")
            if not content:
                continue
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                url = "https://weibo.com" + url
            # 提取作者
            author_el = card.select_one("a.name")
            author_name = ""
            author_url = ""
            if author_el:
                author_name = author_el.get_text(strip=True)
                href = author_el.get("href", "")
                if href and not href.startswith("http"):
                    author_url = "https://weibo.com" + href
                else:
                    author_url = href
            # 提取互动数据
            like_count = 0
            comment_count = 0
            share_count = 0
            actions = card.select("div.card-act li")
            for i, act in enumerate(actions):
                count = self._parse_count(act.get_text())
                if i == 0:
                    share_count = count
                elif i == 1:
                    comment_count = count
                elif i == 2:
                    like_count = count
            results.append({
                "title": content.get_text(strip=True)[:50],
                "url": url,
                "author": author_name,
                "author_url": author_url,
                "like_count": like_count,
                "comment_count": comment_count,
                "share_count": share_count,
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        """抓取微博内容"""
        try:
            resp = await self._request(url)
        except Exception:
            return {}
        soup = BeautifulSoup(resp.text, "lxml")
        content = (soup.select_one("div.weibo-text")
                   or soup.select_one("div.card-text"))
        author_el = soup.select_one("a.name, a.W_texta")
        # 尝试提取互动数据
        like_count = 0
        comment_count = 0
        share_count = 0
        lm = re.search(r'"attitudes_count"\s*:\s*(\d+)', resp.text)
        cm = re.search(r'"comments_count"\s*:\s*(\d+)', resp.text)
        sm = re.search(r'"reposts_count"\s*:\s*(\d+)', resp.text)
        if lm:
            like_count = int(lm.group(1))
        if cm:
            comment_count = int(cm.group(1))
        if sm:
            share_count = int(sm.group(1))
        author_name = ""
        author_url = ""
        if author_el:
            author_name = author_el.get_text(strip=True)
            href = author_el.get("href", "")
            if href and not href.startswith("http"):
                author_url = "https://weibo.com" + href
            else:
                author_url = href
        return {
            "title": content.get_text(strip=True)[:50] if content else "",
            "content": content.get_text(
                separator="\n", strip=True) if content else "",
            "author": author_name,
            "author_url": author_url,
            "publish_time": "",
            "url": url,
            "platform": self.platform,
            "read_count": 0,
            "like_count": like_count,
            "comment_count": comment_count,
            "share_count": share_count,
        }

    async def get_metrics(self, url: str) -> dict:
        """从微博页面提取指标"""
        article = await self.fetch_article(url)
        return {
            "read_count": 0,
            "like_count": article.get("like_count", 0),
            "comment_count": article.get("comment_count", 0),
            "share_count": article.get("share_count", 0),
        }

    async def fetch_author_info(self, author_url: str) -> dict:
        """获取微博用户信息"""
        if not author_url:
            return {}
        try:
            resp = await self._request(author_url)
            soup = BeautifulSoup(resp.text, "lxml")
            name_el = soup.select_one("h1.username, span.name")
            desc_el = soup.select_one("div.pf_intro, p.intro")
            avatar_el = soup.select_one("img.photo, img.avatar")
            follower_count = 0
            fm = re.search(
                r'"followers_count"\s*:\s*(\d+)', resp.text)
            if fm:
                follower_count = int(fm.group(1))
            else:
                fan_el = soup.select_one("a[href$='/fans'] strong")
                if fan_el:
                    follower_count = self._parse_count(
                        fan_el.get_text())
            article_count = 0
            am = re.search(
                r'"statuses_count"\s*:\s*(\d+)', resp.text)
            if am:
                article_count = int(am.group(1))
            verified = False
            vm = re.search(r'"verified"\s*:\s*true', resp.text)
            if vm:
                verified = True
            verified_info = ""
            vi = re.search(
                r'"verified_reason"\s*:\s*"([^"]*)"', resp.text)
            if vi:
                verified_info = vi.group(1)
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
                "verified": verified,
                "verified_info": verified_info,
                "platform": self.platform,
            }
        except Exception:
            return {}
