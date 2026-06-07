"""微信公众号编辑器 Playwright 自动化发布

通过浏览器自动化打开公众号后台编辑器，将排版好的 HTML（含 base64 图片）
粘贴到编辑器中，绕过未认证公众号无法使用 API 的限制。

流程：
1. 加载已保存的 wechat cookie（复用 login_manager.py）
2. 打开 mp.weixin.qq.com → 新建图文编辑页
3. 填写标题
4. 将 HTML 通过 clipboard API 粘贴到编辑器
5. 保持窗口让用户确认/手动调整后保存
"""
import asyncio
import base64
import mimetypes
import os
import re
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from scripts.login_manager import (
    has_valid_cookies,
    load_cookies_to_context,
    interactive_login,
)


class WechatEditorPublisher:
    """Playwright 自动化：将 HTML 粘贴到公众号编辑器"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start(self):
        """启动 Playwright 浏览器并加载 wechat cookie"""
        if not has_valid_cookies("wechat"):
            print("[发布] 未找到微信公众号 cookie，需要先登录...")
            success = await interactive_login("wechat")
            if not success:
                raise RuntimeError(
                    "微信公众号登录失败，请先执行: "
                    "python3 -m scripts.cli login wechat"
                )

        print("[发布] 正在启动 Playwright...", flush=True)
        self._pw = await async_playwright().start()
        print("[发布] 正在打开浏览器...", flush=True)
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        print("[发布] 浏览器已打开，创建上下文...", flush=True)
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        # 授予剪贴板权限
        await self._context.grant_permissions(
            ["clipboard-read", "clipboard-write"]
        )
        await load_cookies_to_context(self._context, "wechat")
        self._page = await self._context.new_page()
        print("[发布] 浏览器已启动，cookie 已加载")

    async def open_editor(self):
        """导航到公众号后台新建图文编辑页"""
        page = self._page
        # 先访问首页确认登录态
        await page.goto(
            "https://mp.weixin.qq.com/", wait_until="domcontentloaded"
        )
        await page.wait_for_timeout(2000)

        # 检查是否需要重新登录
        if "login" in page.url or "scanlogin" in page.url:
            print("[发布] cookie 已过期，需要重新登录...")
            raise RuntimeError(
                "微信 cookie 已过期，请重新执行: "
                "python3 -m scripts.cli login wechat"
            )

        # 直接访问新建图文页面
        await page.goto(
            "https://mp.weixin.qq.com/cgi-bin/appmsg"
            "?t=media/appmsg_edit&action=edit&type=77&token="
            + await self._extract_token(page),
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(3000)
        print("[发布] 已打开图文编辑器")

    async def _extract_token(self, page: Page) -> str:
        """从当前页面 URL 或 cookie 中提取 token"""
        # 尝试从 URL 提取
        url = page.url
        match = re.search(r'token=(\d+)', url)
        if match:
            return match.group(1)
        # 尝试从页面 JS 变量提取
        token = await page.evaluate("""
            () => {
                const m = document.cookie.match(/token=(\\d+)/);
                if (m) return m[1];
                // 尝试从页面脚本中获取
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const tm = s.textContent.match(/token['"\\s:=]+(\\d+)/);
                    if (tm) return tm[1];
                }
                return '';
            }
        """)
        if token:
            return token
        # 从 cgi-bin URL 提取
        match = re.search(r'token=(\d+)', url)
        return match.group(1) if match else ""

    async def paste_content(self, html: str, title: str):
        """填写标题并将 HTML 粘贴到编辑器正文区域"""
        page = self._page

        # === 填写标题 ===
        # 公众号编辑器标题是 .title-editor__input 下的 ProseMirror
        title_editor = page.locator('.title-editor__input .ProseMirror')
        try:
            await title_editor.wait_for(timeout=10000)
            await title_editor.click()
            await page.wait_for_timeout(300)
            await page.keyboard.press("Meta+a")
            await page.keyboard.type(title, delay=20)
            print(f"[发布] 标题已填写: {title}", flush=True)
        except Exception as e:
            print(f"[发布] 标题 locator 失败: {e}", flush=True)
            # 备用：JS 直接写入标题 ProseMirror
            await page.evaluate("""
                (title) => {
                    const el = document.querySelector(
                        '.title-editor__input .ProseMirror'
                    );
                    if (el) {
                        el.focus();
                        el.innerHTML = '<p>' + title + '</p>';
                        el.dispatchEvent(
                            new Event('input', {bubbles: true})
                        );
                    }
                }
            """, title)
            print(f"[发布] 标题已通过 JS 写入", flush=True)

        await page.wait_for_timeout(1000)

        # === 粘贴正文 ===
        # 正文编辑器是 .rich_media_content 下的 ProseMirror
        body_editor = page.locator(
            '.rich_media_content .ProseMirror'
        )
        try:
            await body_editor.wait_for(timeout=10000)
            await body_editor.click()
        except Exception:
            # 兜底：点击第三个 contenteditable
            editors = page.locator('[contenteditable="true"]')
            count = await editors.count()
            if count >= 3:
                await editors.nth(2).click()
            else:
                await editors.last.click()

        await page.wait_for_timeout(500)

        # 通过 ClipboardEvent 粘贴 HTML 到正文
        paste_ok = await page.evaluate("""
            (html) => {
                const editor = document.querySelector(
                    '.rich_media_content .ProseMirror'
                );
                if (!editor) return false;
                editor.focus();
                const dt = new DataTransfer();
                dt.setData('text/html', html);
                dt.setData('text/plain', '');
                const event = new ClipboardEvent('paste', {
                    clipboardData: dt,
                    bubbles: true,
                    cancelable: true,
                });
                editor.dispatchEvent(event);
                return true;
            }
        """, html)
        await page.wait_for_timeout(2000)

        # 验证粘贴结果
        content_length = await page.evaluate("""
            () => {
                const editor = document.querySelector(
                    '.rich_media_content .ProseMirror'
                );
                return editor ? editor.innerHTML.length : 0;
            }
        """)
        if content_length < 100:
            print("[发布] paste 事件未生效，尝试直接设置 innerHTML...",
                  flush=True)
            await page.evaluate("""
                (html) => {
                    const editor = document.querySelector(
                        '.rich_media_content .ProseMirror'
                    );
                    if (editor) {
                        editor.focus();
                        editor.innerHTML = html;
                        editor.dispatchEvent(
                            new Event('input', {bubbles: true})
                        );
                    }
                }
            """, html)
            await page.wait_for_timeout(1000)

        print("[发布] 正文内容已粘贴到编辑器", flush=True)

    async def save_draft(self):
        """点击「保存为草稿」按钮"""
        page = self._page
        # 等待图片上传（base64 图片编辑器会异步上传到CDN）
        print("[发布] 等待图片上传...", flush=True)
        await page.wait_for_timeout(5000)

        # 点击保存按钮
        save_btn = page.locator('#js_submit')
        try:
            await save_btn.wait_for(timeout=5000)
            await save_btn.click()
            print("[发布] 已点击「保存为草稿」", flush=True)
        except Exception as e:
            print(f"[发布] 点击保存按钮失败: {e}", flush=True)
            # 备用：用 JS 触发点击
            await page.evaluate("""
                () => {
                    const btn = document.querySelector('#js_submit');
                    if (btn) btn.click();
                }
            """)
            print("[发布] 已通过 JS 触发保存", flush=True)

        # 等待保存完成（可能有确认弹窗或保存动画）
        await page.wait_for_timeout(3000)

        # 检查是否有确认弹窗需要点击
        try:
            confirm_btn = page.locator(
                '.weui-desktop-dialog__wrp .weui-desktop-btn_primary, '
                '.dialog_wrp .btn_primary'
            )
            if await confirm_btn.count() > 0:
                await confirm_btn.first.click()
                print("[发布] 已确认弹窗", flush=True)
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        print("[发布] 草稿保存完成！", flush=True)

    async def wait_for_user(self):
        """等待用户确认内容并手动保存，关闭窗口后退出"""
        print("\n" + "=" * 50)
        print("[发布] 内容已填入编辑器，请在浏览器中：")
        print("  1. 检查标题和正文排版")
        print("  2. 等待图片自动上传完成")
        print("  3. 手动点击「保存草稿」或「发布」")
        print("  4. 完成后关闭浏览器窗口")
        print("=" * 50 + "\n")

        # 等待浏览器被关闭或页面被用户关闭
        try:
            while True:
                await asyncio.sleep(2)
                try:
                    # 检查页面是否还存在
                    _ = self._page.url
                except Exception:
                    break
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        print("[发布] 浏览器已关闭，流程结束")

    async def close(self):
        """清理资源"""
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass


def embed_local_images_as_base64(html: str, md_file_path: str) -> str:
    """将 HTML 中的本地图片路径替换为 base64 data URI

    公众号编辑器会自动将 base64 图片上传到其 CDN。

    Args:
        html: 包含本地图片 src 的 HTML 内容
        md_file_path: Markdown 文件路径（用于解析相对路径）

    Returns:
        图片已嵌入为 base64 的 HTML
    """
    md_dir = os.path.dirname(os.path.abspath(md_file_path))

    def replace_img_src(match):
        full_tag = match.group(0)
        src = match.group(1)
        # 已经是网络地址或 data URI，跳过
        if src.startswith(("http://", "https://", "data:")):
            return full_tag
        # 解析本地路径
        img_path = (
            os.path.join(md_dir, src) if not os.path.isabs(src) else src
        )
        img_path = os.path.normpath(img_path)
        if not os.path.exists(img_path):
            print(f"[警告] 图片不存在，跳过: {img_path}")
            return full_tag
        # 读取并编码为 base64
        mime_type = mimetypes.guess_type(img_path)[0] or "image/jpeg"
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{img_data}"
        return full_tag.replace(src, data_uri)

    # 匹配 <img src="..."> 中的 src
    return re.sub(r'<img\s+[^>]*src="([^"]+)"', replace_img_src, html)


async def publish_to_wechat_editor(
    md_file_path: str,
    title: str,
    html: str,
):
    """完整发布流程：启动浏览器 → 打开编辑器 → 粘贴内容 → 保存草稿

    Args:
        md_file_path: Markdown 文件路径（用于解析图片路径）
        title: 文章标题
        html: 已转换的排版 HTML
    """
    # 嵌入本地图片为 base64
    html_with_images = embed_local_images_as_base64(html, md_file_path)

    publisher = WechatEditorPublisher(headless=False)
    try:
        await publisher.start()
        await publisher.open_editor()
        await publisher.paste_content(html_with_images, title)
        await publisher.save_draft()
    finally:
        await publisher.close()
