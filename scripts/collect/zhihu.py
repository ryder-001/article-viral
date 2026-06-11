"""知乎采集器 - 通过 Playwright 浏览器搜索获取高赞回答和文章"""
import re
from bs4 import BeautifulSoup
from .base import BaseCollector


class ZhihuCollector(BaseCollector):
    platform = "zhihu"
    SEARCH_URL = "https://www.zhihu.com/search"
    # 知乎搜索 API（不需要登录，返回 JSON）
    API_URL = "https://www.zhihu.com/api/v4/search_v3"

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
        """通过知乎 API 搜索（更稳定）"""
        results = []
        # 先尝试 API
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.zhihu.com/search",
        }
        params = {
            "t": "general",
            "q": keyword,
            "correction": "1",
            "offset": "0",
            "limit": str(min(max_results, 20)),
        }
        try:
            resp = await self._request(
                self.API_URL, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    obj = item.get("object", {})
                    if not obj:
                        continue
                    obj_type = obj.get("type", "")
                    title = ""
                    url = ""
                    author = ""
                    author_url = ""
                    like_count = 0

                    if obj_type == "answer":
                        question = obj.get("question", {})
                        title = question.get("title", "") or obj.get("title", "")
                        url = f"https://www.zhihu.com/question/{question.get('id', '')}/answer/{obj.get('id', '')}"
                        like_count = obj.get("voteup_count", 0)
                    elif obj_type == "article":
                        title = obj.get("title", "")
                        url = obj.get("url", "") or f"https://zhuanlan.zhihu.com/p/{obj.get('id', '')}"
                        like_count = obj.get("voteup_count", 0)
                    else:
                        continue

                    author_info = obj.get("author", {})
                    if author_info:
                        author = author_info.get("name", "")
                        author_url = f"https://www.zhihu.com/people/{author_info.get('url_token', '')}"

                    if title:
                        # 清理 HTML 标签
                        title = re.sub(r"<[^>]+>", "", title)
                        results.append({
                            "title": title,
                            "url": url,
                            "author": author,
                            "author_url": author_url,
                            "like_count": like_count,
                            "platform": self.platform,
                        })
                    if len(results) >= max_results:
                        break
        except Exception:
            pass

        # API 失败则 fallback 到 HTML 解析
        if not results:
            results = await self._search_html(keyword, max_results)

        return results

    async def _search_html(self, keyword: str, max_results: int) -> list[dict]:
        """HTML fallback（知乎搜索页解析）"""
        results = []
        params = {"type": "content", "q": keyword}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.ContentItem"):
            title_el = (item.select_one("h2")
                        or item.select_one("a.ContentItem-title"))
            link = item.select_one("a[data-za-detail-view-path-module]")
            if not title_el:
                continue
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                url = "https://www.zhihu.com" + url
            vote_el = item.select_one("button.VoteButton--up")
            like_count = 0
            if vote_el:
                like_count = self._parse_count(vote_el.get_text())
            author_el = item.select_one("span.AuthorInfo-name a")
            author_name = ""
            author_url = ""
            if author_el:
                author_name = author_el.get_text(strip=True)
                href = author_el.get("href", "")
                if href and not href.startswith("http"):
                    author_url = "https://www.zhihu.com" + href
                else:
                    author_url = href
            results.append({
                "title": title_el.get_text(strip=True),
                "url": url,
                "author": author_name,
                "author_url": author_url,
                "like_count": like_count,
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        """抓取知乎文章/回答"""
        try:
            resp = await self._request(url)
        except Exception:
            return {}
        soup = BeautifulSoup(resp.text, "lxml")
        title = (soup.select_one("h1.QuestionHeader-title")
                 or soup.select_one("h1"))
        content = (soup.select_one("div.RichContent-inner")
                   or soup.select_one("article"))
        author_el = soup.select_one("span.AuthorInfo-name a")
        like_count = 0
        comment_count = 0
        vote_el = soup.select_one("button.VoteButton--up")
        if vote_el:
            like_count = self._parse_count(vote_el.get_text())
        comment_el = soup.select_one(
            "button.ContentItem-action--openComment")
        if comment_el:
            comment_count = self._parse_count(comment_el.get_text())
        if not like_count:
            lc = re.search(r'"voteupCount"\s*:\s*(\d+)', resp.text)
            if lc:
                like_count = int(lc.group(1))
        if not comment_count:
            cc = re.search(r'"commentCount"\s*:\s*(\d+)', resp.text)
            if cc:
                comment_count = int(cc.group(1))
        author_name = ""
        author_url = ""
        if author_el:
            author_name = author_el.get_text(strip=True)
            href = author_el.get("href", "")
            if href and not href.startswith("http"):
                author_url = "https://www.zhihu.com" + href
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
            "read_count": 0,
            "like_count": like_count,
            "comment_count": comment_count,
        }

    async def get_metrics(self, url: str) -> dict:
        """从文章页面提取指标"""
        article = await self.fetch_article(url)
        return {
            "read_count": 0,
            "like_count": article.get("like_count", 0),
            "comment_count": article.get("comment_count", 0),
            "share_count": 0,
        }

    async def fetch_author_info(self, author_url: str) -> dict:
        """获取知乎用户信息"""
        if not author_url:
            return {}
        try:
            resp = await self._request(author_url)
            soup = BeautifulSoup(resp.text, "lxml")
            name_el = soup.select_one("span.ProfileHeader-name")
            desc_el = soup.select_one(
                "span.RichText.ProfileHeader-headline")
            avatar_el = soup.select_one("img.Avatar.ProfileHeader-avatar")
            follower_count = 0
            follower_el = soup.select_one(
                "a[href$='/followers'] strong")
            if follower_el:
                follower_count = self._parse_count(
                    follower_el.get_text())
            else:
                fm = re.search(
                    r'"followerCount"\s*:\s*(\d+)', resp.text)
                if fm:
                    follower_count = int(fm.group(1))
            answer_count = 0
            am = re.search(r'"answerCount"\s*:\s*(\d+)', resp.text)
            if am:
                answer_count = int(am.group(1))
            total_like = 0
            lm = re.search(r'"voteupCount"\s*:\s*(\d+)', resp.text)
            if lm:
                total_like = int(lm.group(1))
            return {
                "name": name_el.get_text(strip=True) if name_el else "",
                "author_url": author_url,
                "avatar": avatar_el.get("src", "") if avatar_el else "",
                "description": desc_el.get_text(
                    strip=True) if desc_el else "",
                "follower_count": follower_count,
                "article_count": answer_count,
                "total_read_count": total_like,
                "level": "",
                "verified": False,
                "verified_info": "",
                "platform": self.platform,
            }
        except Exception:
            return {}
