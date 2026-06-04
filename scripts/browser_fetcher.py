"""基于 Playwright 浏览器自动化的指标采集器

用于获取各平台文章的真实阅读量、点赞、评论、粉丝等指标数据。
静态 HTTP 请求无法拿到 JS 渲染的动态数据，需要真实浏览器环境。
"""
import asyncio
import re
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page
from scripts.login_manager import load_cookies_to_context, has_valid_cookies


class BrowserMetricsFetcher:
    """浏览器自动化指标获取器"""

    def __init__(self, headless: bool = True, timeout: int = 15000):
        self.headless = headless
        self.timeout = timeout
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def start(self):
        """启动浏览器"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless
        )

    async def close(self):
        """关闭浏览器"""
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
        # 加载已保存的 cookie
        if platform and has_valid_cookies(platform):
            await load_cookies_to_context(context, platform)
        page = await context.new_page()
        page.set_default_timeout(self.timeout)
        return page

    def _parse_count(self, text: str) -> int:
        """解析中文数量格式"""
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

    async def get_wechat_metrics(self, url: str) -> dict:
        """获取微信公众号文章指标（需要从搜狗跳转到微信原文）"""
        page = await self._new_page("wechat")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            # 微信文章页指标在 JS 渲染后出现
            read_count = 0
            like_count = 0
            # 阅读量 - 在看数
            read_el = await page.query_selector(
                "#readNum3, #readNum, span.read_num_text")
            if read_el:
                text = await read_el.inner_text()
                read_count = self._parse_count(text)
            # 点赞/在看
            like_el = await page.query_selector(
                "#likeNum, span.like_num, #like_num")
            if like_el:
                text = await like_el.inner_text()
                like_count = self._parse_count(text)
            # 也试试从页面变量中获取
            if not read_count:
                try:
                    read_count = await page.evaluate(
                        "() => window.read_num || 0")
                except Exception:
                    pass
            return {
                "read_count": read_count,
                "like_count": like_count,
                "comment_count": 0,
                "share_count": 0,
            }
        except Exception as e:
            return {"read_count": 0, "like_count": 0,
                    "comment_count": 0, "share_count": 0,
                    "error": str(e)}
        finally:
            await page.context.close()

    async def get_toutiao_metrics(self, url: str) -> dict:
        """获取今日头条文章指标"""
        page = await self._new_page("toutiao")
        try:
            await page.goto(url, wait_until="networkidle",
                            timeout=self.timeout)
            await page.wait_for_timeout(3000)
            data = await page.evaluate(r'''() => {
                const body = document.body.innerText;
                const commentMatch = body.match(/评论\s*(\d+)/);
                const readMatch = body.match(/阅读\s*([\d.]+[万亿]?)/);
                const playMatch = body.match(/([\d.]+[万亿]?)次播放/);
                const timeMatch = body.match(
                    /(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/);
                const sourceMatch = body.match(
                    /\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\xb7(.+)/);
                function parseCount(text) {
                    if (!text) return 0;
                    text = text.replace(/,/g, '').replace('+', '');
                    if (text.includes('万'))
                        return Math.round(
                            parseFloat(text) * 10000);
                    if (text.includes('亿'))
                        return Math.round(
                            parseFloat(text) * 100000000);
                    return parseInt(text) || 0;
                }
                return {
                    comment_count: commentMatch
                        ? parseInt(commentMatch[1]) : 0,
                    read_count: readMatch
                        ? parseCount(readMatch[1])
                        : (playMatch ? parseCount(playMatch[1]) : 0),
                    publish_time: timeMatch ? timeMatch[1] : '',
                    author: sourceMatch ? sourceMatch[1].trim() : '',
                };
            }''')
            return {
                "read_count": data.get("read_count", 0),
                "like_count": 0,
                "comment_count": data.get("comment_count", 0),
                "share_count": 0,
                "author": data.get("author", ""),
                "publish_time": data.get("publish_time", ""),
            }
        except Exception as e:
            return {"read_count": 0, "like_count": 0,
                    "comment_count": 0, "share_count": 0,
                    "error": str(e)}
        finally:
            await page.context.close()

    async def get_baijiahao_metrics(self, url: str) -> dict:
        """获取百家号文章指标"""
        page = await self._new_page("baijiahao")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            read_count = 0
            like_count = 0
            comment_count = 0
            # 百家号阅读量
            read_el = await page.query_selector(
                "span.read-num, span[class*='read'], "
                "em.view-count, span.article-read-count")
            if read_el:
                read_count = self._parse_count(await read_el.inner_text())
            like_el = await page.query_selector(
                "span.like-num, span[class*='praise'], "
                "span[class*='like'] em")
            if like_el:
                like_count = self._parse_count(await like_el.inner_text())
            comment_el = await page.query_selector(
                "span.comment-num, span[class*='comment'] em")
            if comment_el:
                comment_count = self._parse_count(
                    await comment_el.inner_text())
            # 从脚本数据兜底
            if not read_count:
                try:
                    data = await page.evaluate("""() => {
                        const scripts = document.querySelectorAll('script');
                        for (const s of scripts) {
                            const t = s.textContent;
                            if (t.includes('readCount') ||
                                t.includes('read_count')) {
                                const rc = t.match(
                                    /["']?readCount["']?\s*:\s*(\d+)/);
                                const lc = t.match(
                                    /["']?likeCount["']?\s*:\s*(\d+)/);
                                const cc = t.match(
                                    /["']?commentCount["']?\s*:\s*(\d+)/);
                                return {
                                    read: rc ? parseInt(rc[1]) : 0,
                                    like: lc ? parseInt(lc[1]) : 0,
                                    comment: cc ? parseInt(cc[1]) : 0
                                };
                            }
                        }
                        return {read: 0, like: 0, comment: 0};
                    }""")
                    read_count = data.get("read", 0)
                    like_count = like_count or data.get("like", 0)
                    comment_count = comment_count or data.get("comment", 0)
                except Exception:
                    pass
            return {
                "read_count": read_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "share_count": 0,
            }
        except Exception as e:
            return {"read_count": 0, "like_count": 0,
                    "comment_count": 0, "share_count": 0,
                    "error": str(e)}
        finally:
            await page.context.close()

    async def get_zhihu_metrics(self, url: str) -> dict:
        """获取知乎文章/回答指标"""
        page = await self._new_page("zhihu")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            like_count = 0
            comment_count = 0
            # 赞同数
            like_el = await page.query_selector(
                "button.VoteButton--up, button[aria-label*='赞同']")
            if like_el:
                like_count = self._parse_count(await like_el.inner_text())
            # 评论数
            comment_el = await page.query_selector(
                "button[class*='CommentButton'], "
                "a[class*='comment'] span")
            if comment_el:
                comment_count = self._parse_count(
                    await comment_el.inner_text())
            # 从 initial_data 获取
            if not like_count:
                try:
                    data = await page.evaluate("""() => {
                        if (window.__INITIAL_DATA__) {
                            const d = window.__INITIAL_DATA__;
                            // 回答页面
                            const answers = d?.initialState?.entities
                                ?.answers || {};
                            for (const k in answers) {
                                return {
                                    like: answers[k].voteupCount || 0,
                                    comment: answers[k].commentCount || 0
                                };
                            }
                        }
                        return {like: 0, comment: 0};
                    }""")
                    like_count = data.get("like", 0)
                    comment_count = comment_count or data.get("comment", 0)
                except Exception:
                    pass
            return {
                "read_count": 0,
                "like_count": like_count,
                "comment_count": comment_count,
                "share_count": 0,
            }
        except Exception as e:
            return {"read_count": 0, "like_count": 0,
                    "comment_count": 0, "share_count": 0,
                    "error": str(e)}
        finally:
            await page.context.close()

    async def get_weibo_metrics(self, url: str) -> dict:
        """获取微博指标"""
        page = await self._new_page("weibo")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            like_count = 0
            comment_count = 0
            share_count = 0
            try:
                data = await page.evaluate("""() => {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const t = s.textContent;
                        if (t.includes('attitudes_count')) {
                            const lm = t.match(
                                /"attitudes_count"\s*:\s*(\d+)/);
                            const cm = t.match(
                                /"comments_count"\s*:\s*(\d+)/);
                            const sm = t.match(
                                /"reposts_count"\s*:\s*(\d+)/);
                            return {
                                like: lm ? parseInt(lm[1]) : 0,
                                comment: cm ? parseInt(cm[1]) : 0,
                                share: sm ? parseInt(sm[1]) : 0
                            };
                        }
                    }
                    return {like: 0, comment: 0, share: 0};
                }""")
                like_count = data.get("like", 0)
                comment_count = data.get("comment", 0)
                share_count = data.get("share", 0)
            except Exception:
                pass
            return {
                "read_count": 0,
                "like_count": like_count,
                "comment_count": comment_count,
                "share_count": share_count,
            }
        except Exception as e:
            return {"read_count": 0, "like_count": 0,
                    "comment_count": 0, "share_count": 0,
                    "error": str(e)}
        finally:
            await page.context.close()

    async def get_author_info_toutiao(self, author_url: str) -> dict:
        """通过浏览器获取头条号作者信息"""
        page = await self._new_page("toutiao")
        try:
            await page.goto(author_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            name = ""
            description = ""
            follower_count = 0
            avatar = ""
            # 名称
            name_el = await page.query_selector(
                "span.name, h1[class*='name'], div[class*='userName']")
            if name_el:
                name = (await name_el.inner_text()).strip()
            # 简介
            desc_el = await page.query_selector(
                "span.desc, p[class*='desc'], div[class*='intro']")
            if desc_el:
                description = (await desc_el.inner_text()).strip()
            # 头像
            avatar_el = await page.query_selector(
                "img.avatar, img[class*='avatar'], img[class*='Avatar']")
            if avatar_el:
                avatar = await avatar_el.get_attribute("src") or ""
            # 粉丝数
            fan_el = await page.query_selector(
                "span[class*='fan'], span[class*='follower'], "
                "div[class*='fans'] span")
            if fan_el:
                follower_count = self._parse_count(
                    await fan_el.inner_text())
            if not follower_count:
                try:
                    follower_count = await page.evaluate("""() => {
                        const t = document.body.innerText;
                        const m = t.match(/粉丝[：:\s]*([\\d.]+[万亿]?)/);
                        if (m) {
                            let v = m[1];
                            if (v.includes('万'))
                                return Math.round(
                                    parseFloat(v) * 10000);
                            if (v.includes('亿'))
                                return Math.round(
                                    parseFloat(v) * 100000000);
                            return parseInt(v) || 0;
                        }
                        return 0;
                    }""")
                except Exception:
                    pass
            return {
                "name": name,
                "author_url": author_url,
                "avatar": avatar,
                "description": description,
                "follower_count": follower_count,
                "article_count": 0,
                "total_read_count": 0,
                "platform": "toutiao",
            }
        except Exception:
            return {}
        finally:
            await page.context.close()

    async def get_metrics(self, url: str, platform: str) -> dict:
        """统一入口，根据平台分发"""
        dispatch = {
            "wechat": self.get_wechat_metrics,
            "toutiao": self.get_toutiao_metrics,
            "baijiahao": self.get_baijiahao_metrics,
            "zhihu": self.get_zhihu_metrics,
            "weibo": self.get_weibo_metrics,
        }
        handler = dispatch.get(platform)
        if handler:
            return await handler(url)
        return {"read_count": 0, "like_count": 0,
                "comment_count": 0, "share_count": 0}

