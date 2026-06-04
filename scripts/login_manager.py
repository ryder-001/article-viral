"""交互式登录管理 - 弹出浏览器窗口让用户登录，保存 cookie 供后续使用"""
import asyncio
import json
import os
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext


COOKIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "cookies"
)

# 各平台登录页
PLATFORM_LOGIN_URLS = {
    "toutiao": "https://www.toutiao.com/",
    "zhihu": "https://www.zhihu.com/signin",
    "weibo": "https://weibo.com/login.php",
    "wechat": "https://mp.weixin.qq.com/",
    "baijiahao": "https://baijiahao.baidu.com/",
}

# 各平台验证登录成功的检测方式
PLATFORM_CHECK = {
    "toutiao": "https://www.toutiao.com/",
    "zhihu": "https://www.zhihu.com/",
    "weibo": "https://weibo.com/",
    "wechat": "https://mp.weixin.qq.com/",
    "baijiahao": "https://baijiahao.baidu.com/",
}


def get_cookie_path(platform: str) -> str:
    os.makedirs(COOKIES_DIR, exist_ok=True)
    return os.path.join(COOKIES_DIR, f"{platform}_cookies.json")


def has_valid_cookies(platform: str) -> bool:
    """检查是否有已保存的 cookie"""
    path = get_cookie_path(platform)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r") as f:
            cookies = json.load(f)
        return len(cookies) > 0
    except Exception:
        return False


async def interactive_login(platform: str) -> bool:
    """弹出浏览器窗口让用户手动登录，登录成功后保存 cookie"""
    login_url = PLATFORM_LOGIN_URLS.get(platform)
    if not login_url:
        print(f"[登录] 不支持的平台: {platform}")
        return False

    print(f"[登录] 即将打开 {platform} 登录页面...")
    print(f"[登录] 请在浏览器中完成登录，登录成功后脚本会自动保存 cookie")
    print(f"[登录] 如果已经完成登录，请关闭浏览器窗口")

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
    )
    page = await context.new_page()

    try:
        await page.goto(login_url, wait_until="domcontentloaded")
        # 等待用户完成登录——轮询检测页面变化
        print(f"[登录] 浏览器已打开，请登录 {platform}...")
        print("[登录] 登录完成后，等待 5 秒自动保存...")

        # 最长等待 5 分钟
        for _ in range(60):
            await asyncio.sleep(5)
            # 检测页面是否还存在（用户可能关了窗口）
            try:
                current_url = page.url
            except Exception:
                break
            # 简单检测：如果不再是登录页面就认为登录成功
            if _is_logged_in(platform, current_url):
                print(f"[登录] 检测到登录成功！")
                break
        else:
            print("[登录] 等待超时，尝试保存当前 cookie...")

        # 保存 cookies
        cookies = await context.cookies()
        if cookies:
            cookie_path = get_cookie_path(platform)
            with open(cookie_path, "w") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"[登录] 已保存 {len(cookies)} 个 cookie 到 {cookie_path}")
            return True
        else:
            print("[登录] 未获取到 cookie")
            return False
    except Exception as e:
        print(f"[登录] 登录过程出错: {e}")
        return False
    finally:
        await browser.close()
        await pw.stop()


def _is_logged_in(platform: str, current_url: str) -> bool:
    """根据当前 URL 判断是否已经登录成功"""
    checks = {
        "toutiao": lambda u: "login" not in u and "toutiao.com" in u,
        "zhihu": lambda u: "signin" not in u and "zhihu.com" in u,
        "weibo": lambda u: "login" not in u and "weibo.com" in u,
        "wechat": lambda u: "cgi-bin" in u or "home" in u,
        "baijiahao": lambda u: "author" in u or "bjh" in u,
    }
    checker = checks.get(platform)
    return checker(current_url) if checker else False


async def load_cookies_to_context(
    context: BrowserContext, platform: str
) -> bool:
    """将保存的 cookie 加载到浏览器 context"""
    cookie_path = get_cookie_path(platform)
    if not os.path.exists(cookie_path):
        return False
    try:
        with open(cookie_path, "r") as f:
            cookies = json.load(f)
        if cookies:
            await context.add_cookies(cookies)
            return True
    except Exception:
        pass
    return False


async def ensure_login(platform: str) -> bool:
    """确保已登录：有 cookie 就跳过，没有就弹窗登录"""
    if has_valid_cookies(platform):
        print(f"[登录] {platform} 已有保存的 cookie")
        return True
    return await interactive_login(platform)


def list_saved_logins() -> list[str]:
    """列出所有已保存 cookie 的平台"""
    if not os.path.exists(COOKIES_DIR):
        return []
    platforms = []
    for f in os.listdir(COOKIES_DIR):
        if f.endswith("_cookies.json"):
            platform = f.replace("_cookies.json", "")
            platforms.append(platform)
    return platforms

