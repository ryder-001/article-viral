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
import json
import mimetypes
import os
import re
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from scripts.login_manager import (
    has_valid_cookies,
    load_cookies_to_context,
    interactive_login,
    get_cookie_path,
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
        """启动 Playwright 浏览器并加载 wechat cookie

        使用持久化用户数据目录（launch_persistent_context），让微信后台的
        静态资源（JS/CSS/图片）落到磁盘缓存，第二次起打开页面明显更快，
        同时登录态也能在多次发布间复用。
        """
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
        print("[发布] 正在打开浏览器（持久化缓存）...", flush=True)

        # 持久化用户数据目录：缓存静态资源 + 复用登录态
        profile_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", ".browser_profile",
        )
        os.makedirs(profile_dir, exist_ok=True)

        ctx_kwargs = dict(
            user_data_dir=profile_dir,
            headless=self.headless,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        try:
            self._context = await self._pw.chromium.launch_persistent_context(
                channel="chrome", **ctx_kwargs)
        except Exception:
            # 回退到 playwright 自带 chromium 内核
            self._context = await self._pw.chromium.launch_persistent_context(
                **ctx_kwargs)
        print("[发布] 浏览器已打开（用户数据目录已复用）", flush=True)

        # 授予剪贴板权限
        await self._context.grant_permissions(
            ["clipboard-read", "clipboard-write"]
        )
        await load_cookies_to_context(self._context, "wechat")
        # persistent_context 自带一个初始页面，直接复用，避免多开
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
        print("[发布] 浏览器已启动，cookie 已加载")

    async def open_editor(self):
        """导航到公众号后台新建图文编辑页"""
        page = self._page
        # 先访问首页确认登录态
        await page.goto(
            "https://mp.weixin.qq.com/", wait_until="commit", timeout=60000
        )
        await page.wait_for_timeout(3000)

        # 检查是否需要重新登录——不再直接报错退出，而是暂停等用户扫码
        if self._is_login_page(page.url):
            print("[发布] 检测到需要登录微信公众号...")
            await self._wait_for_manual_login()

        # 直接访问新建图文页面
        await page.goto(
            "https://mp.weixin.qq.com/cgi-bin/appmsg"
            "?t=media/appmsg_edit&action=edit&type=77&token="
            + await self._extract_token(page),
            wait_until="commit",
            timeout=60000,
        )
        await page.wait_for_timeout(4000)

        # 跳转后可能又被打回登录页（cookie 半失效），再兜底等一次
        if self._is_login_page(page.url):
            print("[发布] 打开编辑器时被要求登录...")
            await self._wait_for_manual_login()
            await page.goto(
                "https://mp.weixin.qq.com/cgi-bin/appmsg"
                "?t=media/appmsg_edit&action=edit&type=77&token="
                + await self._extract_token(page),
                wait_until="commit",
                timeout=60000,
            )
            await page.wait_for_timeout(4000)

        print("[发布] 已打开图文编辑器")

        # 关闭干扰性弹窗（未授权切换账号 / 赞赏开通等），并等编辑器渲染
        await self._dismiss_dialogs()
        await self._wait_editor_ready()

    @staticmethod
    def _is_login_page(url: str) -> bool:
        """判断当前 URL 是否为登录/扫码页"""
        u = (url or "").lower()
        return ("login" in u) or ("scanlogin" in u) or ("/safe/" in u)

    async def _wait_for_manual_login(self, timeout_sec: int = 300):
        """暂停在当前浏览器窗口，等待用户手动扫码登录后继续。

        不关闭浏览器，轮询检测是否已进入后台（URL 含 token/cgi-bin/home）。
        登录成功后把最新 cookie 回写到本地，供下次复用。
        """
        page = self._page
        print("\n" + "=" * 50)
        print("[发布] 请在已打开的浏览器窗口中扫码登录微信公众号")
        print(f"[发布] 登录成功后会自动继续（最长等待 {timeout_sec} 秒）")
        print("[发布] 请勿关闭浏览器窗口")
        print("=" * 50 + "\n", flush=True)

        waited = 0
        interval = 3
        while waited < timeout_sec:
            await asyncio.sleep(interval)
            waited += interval
            try:
                current = page.url
            except Exception:
                # 页面在导航中，稍后重试
                continue
            # 进入后台首页或带 token 即视为登录成功
            if (not self._is_login_page(current)) and (
                "token=" in current
                or "/cgi-bin/home" in current
                or "/cgi-bin/" in current
            ):
                print(f"[发布] 检测到登录成功！({current.split('?')[0]})",
                      flush=True)
                await self._save_cookies()
                # 给后台首页留一点渲染时间
                await page.wait_for_timeout(2000)
                return
            # 还停在首页根路径时，主动探一次后台，触发跳转
            if current.rstrip("/").endswith("mp.weixin.qq.com"):
                try:
                    await page.goto(
                        "https://mp.weixin.qq.com/cgi-bin/home",
                        wait_until="commit", timeout=30000,
                    )
                    await page.wait_for_timeout(1500)
                    if "token=" in page.url:
                        print("[发布] 检测到登录成功！", flush=True)
                        await self._save_cookies()
                        return
                except Exception:
                    pass

        raise RuntimeError(
            f"等待登录超时（{timeout_sec}秒）。请重新运行发布命令，"
            "或先执行 python3 -m scripts.cli login wechat"
        )

    async def _save_cookies(self):
        """把当前 context 的 cookie 回写到本地，供下次复用"""
        try:
            cookies = await self._context.cookies()
            if cookies:
                path = get_cookie_path("wechat")
                with open(path, "w") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                print(f"[发布] 已更新 wechat cookie（{len(cookies)} 条）",
                      flush=True)
        except Exception as e:
            print(f"[发布] 保存 cookie 失败（不影响本次发布）: {e}",
                  flush=True)

    async def _dismiss_dialogs(self):
        """关闭编辑器加载时的非阻断弹窗（点「我知道了」「暂不开通」「取消」）"""
        page = self._page
        for _ in range(3):
            clicked = await page.evaluate(r"""
            () => {
              let hit = 0;
              const kw = ['我知道了','暂不开通','取消','知道了'];
              const btns = [...document.querySelectorAll(
                '.weui-desktop-dialog button, .weui-desktop-dialog a,'
                + ' .weui-desktop-btn')];
              for (const b of btns) {
                const t = (b.innerText||'').trim();
                if (kw.some(k => t === k)) { b.click(); hit++; }
              }
              return hit;
            }
            """)
            if not clicked:
                break
            await page.wait_for_timeout(800)
        print("[发布] 已尝试关闭干扰弹窗")

    async def _wait_editor_ready(self):
        """轮询等待标题/正文 ProseMirror 渲染出来（最长 ~40s）。

        若过程中页面被重定向到登录页（执行上下文被销毁），
        则暂停等待用户扫码登录后重新打开编辑器，而不是直接崩溃。
        """
        page = self._page
        for _ in range(20):
            # 渲染轮询期间页面可能正在跳转，evaluate 会抛
            # "Execution context was destroyed"，这里捕获后判断是否跳到登录页
            try:
                cnt = await page.evaluate(
                    "() => document.querySelectorAll('.ProseMirror').length"
                )
            except Exception:
                await page.wait_for_timeout(1500)
                if self._is_login_page(page.url):
                    print("[发布] 编辑器加载中被打回登录页，等待扫码登录...")
                    await self._wait_for_manual_login()
                    await self.open_editor()
                    return
                continue

            if cnt and cnt >= 2:
                print(f"[发布] 编辑器已就绪（ProseMirror={cnt}）")
                return
            await page.wait_for_timeout(2000)

            # 没渲染出来时，也可能是悄悄跳到了登录页
            if self._is_login_page(page.url):
                print("[发布] 检测到登录页，等待扫码登录...")
                await self._wait_for_manual_login()
                await self.open_editor()
                return
        print("[发布] 警告：等待编辑器渲染超时，继续尝试")


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
        # 标题是带 placeholder「请在这里输入标题」的 ProseMirror（第一个）
        title_editor = page.locator(
            '.ProseMirror[data-placeholder*="标题"]'
        ).first
        try:
            await title_editor.wait_for(timeout=15000)
            await title_editor.click()
            await page.wait_for_timeout(300)
            await page.keyboard.press("Meta+a")
            await page.keyboard.type(title, delay=20)
            print(f"[发布] 标题已填写: {title}", flush=True)
        except Exception as e:
            print(f"[发布] 标题 locator 失败: {e}", flush=True)
            # 备用：JS 写入第一个 ProseMirror
            await page.evaluate("""
                (title) => {
                    const els = document.querySelectorAll('.ProseMirror');
                    const el = [...els].find(
                        e => (e.getAttribute('data-placeholder')||'')
                              .includes('标题')) || els[0];
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
        # 正文是正文区 ProseMirror（标题之外的可编辑 ProseMirror）
        body_sel = (
            "() => [...document.querySelectorAll('.ProseMirror')]"
            ".find(e => !(e.getAttribute('data-placeholder')||'')"
            ".includes('标题'))"
        )
        # 先点击正文区获取焦点
        try:
            body_editor = page.locator('.ProseMirror').nth(1)
            await body_editor.wait_for(timeout=10000)
            await body_editor.click()
        except Exception:
            editors = page.locator('.ProseMirror')
            if await editors.count() >= 2:
                await editors.nth(1).click()
            else:
                await editors.last.click()

        await page.wait_for_timeout(500)

        # 通过 ClipboardEvent 粘贴 HTML 到正文
        await page.evaluate("""
            (html) => {
                const editor = [...document.querySelectorAll('.ProseMirror')]
                    .find(e => !(e.getAttribute('data-placeholder')||'')
                                .includes('标题'));
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
                const editor = [...document.querySelectorAll('.ProseMirror')]
                    .find(e => !(e.getAttribute('data-placeholder')||'')
                                .includes('标题'));
                return editor ? editor.innerHTML.length : 0;
            }
        """)
        if content_length < 100:
            print("[发布] paste 事件未生效，尝试直接设置 innerHTML...",
                  flush=True)
            await page.evaluate("""
                (html) => {
                    const editor =
                        [...document.querySelectorAll('.ProseMirror')]
                        .find(e => !(e.getAttribute('data-placeholder')||'')
                                    .includes('标题'));
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

        # 保存前再清一次可能弹出的干扰弹窗
        await self._dismiss_dialogs()

        # 点击「保存为草稿」按钮（该按钮无 id/class，用精确文本定位）
        clicked = False
        try:
            save_btn = page.get_by_text("保存为草稿", exact=True).first
            await save_btn.wait_for(timeout=8000)
            await save_btn.click()
            clicked = True
            print("[发布] 已点击「保存为草稿」", flush=True)
        except Exception as e:
            print(f"[发布] 文本定位保存按钮失败: {e}", flush=True)

        # 兜底：JS 遍历所有按钮按文本点击
        if not clicked:
            clicked = await page.evaluate(r"""
                () => {
                    const els = [...document.querySelectorAll(
                        'button, a, [role=button], .weui-desktop-btn')];
                    const b = els.find(
                        e => (e.innerText||'').trim() === '保存为草稿');
                    if (b) { b.click(); return true; }
                    // 兼容旧版 id
                    const old = document.querySelector('#js_submit');
                    if (old) { old.click(); return true; }
                    return false;
                }
            """)
            print(f"[发布] JS 触发保存: {'成功' if clicked else '未找到按钮'}",
                  flush=True)

        # 等待保存完成（可能有确认弹窗或保存动画）
        await page.wait_for_timeout(4000)

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
            # persistent_context 模式下没有独立 browser，关 context 即可
            if self._context:
                await self._context.close()
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
