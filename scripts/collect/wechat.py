"""微信公众号采集器 - 通过搜狗微信搜索获取文章"""
import re
from bs4 import BeautifulSoup
from .base import BaseCollector


class WechatCollector(BaseCollector):
    platform = "wechat"
    SEARCH_URL = "https://weixin.sogou.com/weixin"

    def _parse_count(self, text: str) -> int:
        """解析数量文本，支持 '1.2万'、'10万+' 等格式"""
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
        results = []
        page = 1
        while len(results) < max_results:
            params = {"type": "2", "query": keyword, "page": str(page)}
            try:
                resp = await self._request(self.SEARCH_URL, params=params)
            except Exception:
                break
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select("div.txt-box")
            if not items:
                break
            for item in items:
                a = item.select_one("h3 a")
                if not a:
                    continue
                url = a.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://weixin.sogou.com" + url
                summary = item.select_one("p.txt-info")
                account = item.select_one("a.account")
                # 搜狗页面有时展示阅读数
                read_el = item.select_one("span.s2")
                read_count = self._parse_count(
                    read_el.get_text()) if read_el else 0
                author_url = ""
                if account:
                    href = account.get("href", "")
                    if href and not href.startswith("http"):
                        author_url = "https://weixin.sogou.com" + href
                    else:
                        author_url = href
                results.append({
                    "title": a.get_text(strip=True),
                    "url": url,
                    "content": summary.get_text(strip=True) if summary else "",
                    "author": account.get_text(strip=True) if account else "",
                    "author_url": author_url,
                    "platform": self.platform,
                    "read_count": read_count,
                })
                if len(results) >= max_results:
                    break
            page += 1
        return results

    async def fetch_article(self, url: str) -> dict:
        """抓取全文并尝试提取阅读指标"""
        try:
            resp = await self._request(url)
            if "antispider" in str(resp.url):
                return {}
            soup = BeautifulSoup(resp.text, "lxml")
            title = soup.select_one("#activity-name")
            content_div = soup.select_one("#js_content")
            author = soup.select_one("#js_name")
            publish_time = soup.select_one("#publish_time")
            # 尝试提取阅读数和点赞数（页面内嵌 JS 变量）
            read_count = 0
            like_count = 0
            page_text = resp.text
            read_match = re.search(
                r'var\s+read_num\s*=\s*["\']?(\d+)', page_text)
            like_match = re.search(
                r'var\s+like_num\s*=\s*["\']?(\d+)', page_text)
            old_like_match = re.search(
                r'var\s+old_like_num\s*=\s*["\']?(\d+)', page_text)
            if read_match:
                read_count = int(read_match.group(1))
            if like_match:
                like_count = int(like_match.group(1))
            elif old_like_match:
                like_count = int(old_like_match.group(1))
            if title or content_div:
                return {
                    "title": title.get_text(strip=True) if title else "",
                    "content": content_div.get_text(
                        separator="\n", strip=True) if content_div else "",
                    "author": author.get_text(strip=True) if author else "",
                    "publish_time": publish_time.get_text(
                        strip=True) if publish_time else "",
                    "url": url,
                    "platform": self.platform,
                    "read_count": read_count,
                    "like_count": like_count,
                }
        except Exception:
            pass
        return {}

    async def get_metrics(self, url: str) -> dict:
        """从文章页面提取阅读指标"""
        try:
            resp = await self._request(url)
            if "antispider" in str(resp.url):
                return {}
            page_text = resp.text
            read_count = 0
            like_count = 0
            comment_count = 0
            read_match = re.search(
                r'var\s+read_num\s*=\s*["\']?(\d+)', page_text)
            like_match = re.search(
                r'var\s+(?:like_num|old_like_num)\s*=\s*["\']?(\d+)',
                page_text)
            comment_match = re.search(
                r'var\s+comment_num\s*=\s*["\']?(\d+)', page_text)
            if read_match:
                read_count = int(read_match.group(1))
            if like_match:
                like_count = int(like_match.group(1))
            if comment_match:
                comment_count = int(comment_match.group(1))
            return {
                "read_count": read_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "share_count": 0,
            }
        except Exception:
            return {"read_count": 0, "like_count": 0,
                    "comment_count": 0, "share_count": 0}

    async def fetch_author_info(self, author_url: str) -> dict:
        """通过搜狗微信公众号主页获取作者信息"""
        if not author_url:
            return {}
        try:
            resp = await self._request(author_url)
            soup = BeautifulSoup(resp.text, "lxml")
            name = soup.select_one("strong.profile_nickname")
            desc = soup.select_one("p.profile_desc")
            avatar = soup.select_one("img.profile_avatar")
            # 认证信息
            verified_el = soup.select_one("i.icon_verify")
            verified_info_el = soup.select_one("p.profile_desc_value")
            return {
                "name": name.get_text(strip=True) if name else "",
                "author_url": author_url,
                "avatar": avatar.get("src", "") if avatar else "",
                "description": desc.get_text(strip=True) if desc else "",
                "follower_count": 0,
                "article_count": 0,
                "total_read_count": 0,
                "level": "",
                "verified": bool(verified_el),
                "verified_info": verified_info_el.get_text(
                    strip=True) if verified_info_el else "",
                "platform": self.platform,
            }
        except Exception:
            return {}
