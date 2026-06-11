"""浏览器全文内容提取器

打开文章页面，提取完整正文内容（标题、作者、正文、发布时间）。
各平台文章页 DOM 结构不同，需要分平台处理。
"""
import re
from typing import Optional
from playwright.async_api import Page, Browser
from scripts.browser_fetcher import BrowserMetricsFetcher


class ContentExtractor(BrowserMetricsFetcher):
    """基于浏览器的全文内容提取器，继承 BrowserMetricsFetcher 的基础设施"""

    async def extract_content(self, url: str, platform: str) -> dict:
        """统一入口：根据平台提取全文"""
        dispatch = {
            "wechat": self._extract_wechat,
            "toutiao": self._extract_toutiao,
            "baijiahao": self._extract_baijiahao,
            "zhihu": self._extract_zhihu,
            "weibo": self._extract_weibo,
            "sohu": self._extract_sohu,
        }
        handler = dispatch.get(platform, self._extract_generic)
        try:
            return await handler(url)
        except Exception as e:
            return {"error": str(e), "url": url, "platform": platform}

    async def _extract_wechat(self, url: str) -> dict:
        """微信公众号文章全文提取"""
        page = await self._new_page("wechat")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            title = await self._get_text(page, "#activity-name, .rich_media_title")
            author = await self._get_text(page, "#js_name, .rich_media_meta_nickname a")
            publish_time = await self._get_text(page, "#publish_time, em#publish_time")

            # 正文区域
            content = await self._get_text(page, "#js_content, .rich_media_content")

            # 获取指标
            read_count = 0
            read_el = await page.query_selector("#readNum3, #readNum")
            if read_el:
                read_count = self._parse_count(await read_el.inner_text())

            like_count = 0
            like_el = await page.query_selector("#likeNum, #like_num")
            if like_el:
                like_count = self._parse_count(await like_el.inner_text())

            return {
                "title": title.strip() if title else "",
                "author": author.strip() if author else "",
                "content": self._clean_content(content),
                "publish_time": publish_time.strip() if publish_time else "",
                "url": url,
                "platform": "wechat",
                "read_count": read_count,
                "like_count": like_count,
                "comment_count": 0,
                "share_count": 0,
            }
        finally:
            await page.context.close()

    async def _extract_toutiao(self, url: str) -> dict:
        """今日头条文章全文提取"""
        page = await self._new_page("toutiao")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            title = await self._get_text(page, "h1, .article-title, [class*='title']")
            author = await self._get_text(
                page, "a[class*='name'], span[class*='author'], .article-sub .name")

            # 正文：头条文章正文一般在 article 标签里
            content = await self._get_text(
                page, "article, .article-content, [class*='article-body'], "
                      "[class*='content'] .pgc-img-caption")
            if not content or len(content) < 100:
                # fallback: 尝试从整个页面提取
                content = await page.evaluate(r'''() => {
                    const article = document.querySelector('article') ||
                                    document.querySelector('[class*="content"]');
                    if (article) {
                        // 移除脚本和样式
                        article.querySelectorAll('script, style, nav, header, footer')
                            .forEach(el => el.remove());
                        return article.innerText;
                    }
                    return '';
                }''')

            # 指标
            metrics = await page.evaluate(r'''() => {
                const body = document.body.innerText;
                const commentMatch = body.match(/评论\s*(\d+)/);
                const readMatch = body.match(/阅读\s*([\d.]+[万亿]?)/);
                const timeMatch = body.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/);
                return {
                    comment_count: commentMatch ? parseInt(commentMatch[1]) : 0,
                    read_count: readMatch ? readMatch[1] : '0',
                    publish_time: timeMatch ? timeMatch[1] : '',
                };
            }''')

            return {
                "title": title.strip() if title else "",
                "author": author.strip() if author else "",
                "content": self._clean_content(content),
                "publish_time": metrics.get("publish_time", ""),
                "url": url,
                "platform": "toutiao",
                "read_count": self._parse_count(str(metrics.get("read_count", 0))),
                "like_count": 0,
                "comment_count": metrics.get("comment_count", 0),
                "share_count": 0,
            }
        finally:
            await page.context.close()

    async def _extract_baijiahao(self, url: str) -> dict:
        """百家号文章全文提取"""
        page = await self._new_page("baijiahao")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            title = await self._get_text(
                page, "h1, .article-title, [class*='title']")
            author = await self._get_text(
                page, ".author-name, [class*='author'] span, .article-source")

            content = await self._get_text(
                page, ".article-content, #article, [class*='article-body']")
            if not content or len(content) < 100:
                content = await page.evaluate(r'''() => {
                    const el = document.querySelector('[class*="content"]') ||
                               document.querySelector('article');
                    if (el) {
                        el.querySelectorAll('script, style, .related, .recommend')
                            .forEach(e => e.remove());
                        return el.innerText;
                    }
                    return '';
                }''')

            return {
                "title": title.strip() if title else "",
                "author": author.strip() if author else "",
                "content": self._clean_content(content),
                "publish_time": "",
                "url": url,
                "platform": "baijiahao",
                "read_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
            }
        finally:
            await page.context.close()

    async def _extract_zhihu(self, url: str) -> dict:
        """知乎文章/回答全文提取"""
        page = await self._new_page("zhihu")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # 知乎有两种：文章（zhuanlan）和回答（answer）
            is_article = "zhuanlan" in url

            if is_article:
                title = await self._get_text(page, "h1.Post-Title, h1")
                author = await self._get_text(
                    page, ".AuthorInfo-name a, .Post-Author a")
                content = await self._get_text(
                    page, ".Post-RichTextContainer, .RichText")
            else:
                title = await self._get_text(page, "h1.QuestionHeader-title, h1")
                author = await self._get_text(
                    page, ".AuthorInfo-name a, [class*='AuthorInfo'] a")
                content = await self._get_text(
                    page, ".RichContent-inner .RichText, .AnswerItem .RichText")

            # 赞同数
            like_count = 0
            like_el = await page.query_selector(
                "button.VoteButton--up, button[aria-label*='赞同']")
            if like_el:
                like_count = self._parse_count(await like_el.inner_text())

            return {
                "title": title.strip() if title else "",
                "author": author.strip() if author else "",
                "content": self._clean_content(content),
                "publish_time": "",
                "url": url,
                "platform": "zhihu",
                "read_count": 0,
                "like_count": like_count,
                "comment_count": 0,
                "share_count": 0,
            }
        finally:
            await page.context.close()

    async def _extract_weibo(self, url: str) -> dict:
        """微博正文提取"""
        page = await self._new_page("weibo")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # 微博长文
            title = await self._get_text(
                page, "h1.title, .article_title, [class*='title']")
            author = await self._get_text(
                page, "a[class*='name'], .head-info_name, [class*='nick']")
            content = await self._get_text(
                page, ".article_content, .weibo-text, [class*='feed_body'] "
                      "[class*='text'], .WB_text")

            if not content or len(content) < 50:
                # 短微博
                content = await page.evaluate(r'''() => {
                    const el = document.querySelector('[class*="text"]') ||
                               document.querySelector('[class*="content"]');
                    return el ? el.innerText : '';
                }''')

            return {
                "title": title.strip() if title else "",
                "author": author.strip() if author else "",
                "content": self._clean_content(content),
                "publish_time": "",
                "url": url,
                "platform": "weibo",
                "read_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
            }
        finally:
            await page.context.close()

    async def _extract_sohu(self, url: str) -> dict:
        """搜狐号文章全文提取"""
        page = await self._new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            title = await self._get_text(
                page, "h1, .text-title h1, [class*='title']")
            author = await self._get_text(
                page, ".user-info h4, .article-source, [class*='author']")
            content = await self._get_text(
                page, "article, .article-content, #mp-editor, [id*='content']")

            return {
                "title": title.strip() if title else "",
                "author": author.strip() if author else "",
                "content": self._clean_content(content),
                "publish_time": "",
                "url": url,
                "platform": "sohu",
                "read_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
            }
        finally:
            await page.context.close()

    async def _extract_generic(self, url: str) -> dict:
        """通用文章提取（尝试 article/main/content 选择器）"""
        page = await self._new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            title = await self._get_text(page, "h1")
            content = await page.evaluate(r'''() => {
                const el = document.querySelector('article') ||
                           document.querySelector('main') ||
                           document.querySelector('[class*="content"]') ||
                           document.querySelector('[id*="content"]');
                if (el) {
                    el.querySelectorAll('script, style, nav, header, footer, aside')
                        .forEach(e => e.remove());
                    return el.innerText;
                }
                return document.body.innerText.slice(0, 10000);
            }''')

            return {
                "title": title.strip() if title else "",
                "author": "",
                "content": self._clean_content(content),
                "publish_time": "",
                "url": url,
                "platform": "unknown",
                "read_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
            }
        finally:
            await page.context.close()

    async def _get_text(self, page: Page, selector: str) -> str:
        """安全获取元素文本"""
        el = await page.query_selector(selector)
        if el:
            return await el.inner_text()
        return ""

    def _clean_content(self, text: str) -> str:
        """清理正文内容"""
        if not text:
            return ""
        # 去除多余空行
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned.append(line)
        text = "\n".join(cleaned)
        # 去除常见广告/推荐文本
        noise_patterns = [
            r"点击.*?关注.*",
            r"推荐阅读.*",
            r"延伸阅读.*",
            r"相关推荐.*",
            r"热门评论.*",
            r"特别声明.*本文.*",
            r"免责声明.*",
        ]
        for pattern in noise_patterns:
            text = re.sub(pattern, "", text)
        return text.strip()
