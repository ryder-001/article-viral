"""微信公众号发布核心模块

负责：获取 access_token、上传图片、创建草稿、发布草稿。
使用 httpx（项目已有依赖）进行 API 调用。
"""
import os
import re
from typing import Optional
import httpx

WECHAT_API_BASE = "https://api.weixin.qq.com"

# 常见微信 API 错误码
ERROR_CODES = {
    40001: "access_token 无效，请检查 AppID/AppSecret",
    40007: "media_id 无效",
    40008: "图片文件格式不支持",
    40009: "图片文件大小超出限制(2MB)",
    45001: "标题超出限制(64字)",
    45002: "内容超出限制",
    45004: "摘要超出限制(120字)",
    45008: "图文消息超出限制",
    40004: "不合法的媒体文件类型",
    40003: "不合法的 OpenID",
    48001: "接口未授权，请检查公众号权限",
}


def load_wechat_credentials() -> tuple:
    """从 .env 文件加载微信凭证"""
    try:
        from dotenv import dotenv_values
    except ImportError:
        raise RuntimeError(
            "缺少 python-dotenv 依赖，请执行: pip install python-dotenv"
        )
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), ".env"
    )
    if not os.path.exists(env_path):
        raise FileNotFoundError(
            f"未找到 .env 配置文件，请在项目根目录创建 .env 文件并配置：\n"
            f"  WECHAT_APP_ID=你的AppID\n"
            f"  WECHAT_APP_SECRET=你的AppSecret\n"
            f"参考 .env.example"
        )
    config = dotenv_values(env_path)
    app_id = config.get("WECHAT_APP_ID", "").strip()
    app_secret = config.get("WECHAT_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise ValueError(
            ".env 文件中缺少 WECHAT_APP_ID 或 WECHAT_APP_SECRET"
        )
    return app_id, app_secret


def get_access_token(app_id: str, app_secret: str) -> str:
    """获取微信 access_token"""
    url = f"{WECHAT_API_BASE}/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
    }
    resp = httpx.get(url, params=params, timeout=15)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    errcode = data.get("errcode", -1)
    errmsg = ERROR_CODES.get(errcode, data.get("errmsg", "未知错误"))
    raise RuntimeError(f"获取 access_token 失败 [{errcode}]: {errmsg}")


def upload_image(access_token: str, image_path: str) -> str:
    """上传图片到永久素材库（用作封面），返回 media_id"""
    url = f"{WECHAT_API_BASE}/cgi-bin/material/add_material"
    params = {"access_token": access_token, "type": "thumb"}
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    file_size = os.path.getsize(image_path)
    if file_size > 2 * 1024 * 1024:
        raise ValueError(f"图片大小 {file_size/1024/1024:.1f}MB 超出2MB限制")
    with open(image_path, "rb") as f:
        files = {"media": (os.path.basename(image_path), f, "image/jpeg")}
        resp = httpx.post(url, params=params, files=files, timeout=30)
    data = resp.json()
    if "media_id" in data:
        return data["media_id"]
    errcode = data.get("errcode", -1)
    errmsg = ERROR_CODES.get(errcode, data.get("errmsg", "未知错误"))
    raise RuntimeError(f"上传封面图失败 [{errcode}]: {errmsg}")


def upload_content_image(access_token: str, image_path: str) -> str:
    """上传正文内图片到微信CDN，返回图片URL"""
    url = f"{WECHAT_API_BASE}/cgi-bin/media/uploadimg"
    params = {"access_token": access_token}
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    with open(image_path, "rb") as f:
        files = {"media": (os.path.basename(image_path), f, "image/jpeg")}
        resp = httpx.post(url, params=params, files=files, timeout=30)
    data = resp.json()
    if "url" in data:
        return data["url"]
    errcode = data.get("errcode", -1)
    errmsg = ERROR_CODES.get(errcode, data.get("errmsg", "未知错误"))
    raise RuntimeError(f"上传正文图片失败 [{errcode}]: {errmsg}")


def create_draft(access_token: str, title: str, html_content: str,
                 thumb_media_id: str, author: str = "",
                 digest: str = "") -> str:
    """创建公众号草稿，返回 media_id"""
    url = f"{WECHAT_API_BASE}/cgi-bin/draft/add"
    params = {"access_token": access_token}
    article = {
        "title": title[:64],
        "author": author,
        "digest": digest[:120] if digest else "",
        "content": html_content,
        "thumb_media_id": thumb_media_id,
        "show_cover_pic": 1,
        "need_open_comment": 1,
    }
    payload = {"articles": [article]}
    resp = httpx.post(url, params=params, json=payload, timeout=30)
    data = resp.json()
    if "media_id" in data:
        return data["media_id"]
    errcode = data.get("errcode", -1)
    errmsg = ERROR_CODES.get(errcode, data.get("errmsg", "未知错误"))
    raise RuntimeError(f"创建草稿失败 [{errcode}]: {errmsg}")


def publish_draft(access_token: str, media_id: str) -> str:
    """发布草稿，返回 publish_id"""
    url = f"{WECHAT_API_BASE}/cgi-bin/freepublish/submit"
    params = {"access_token": access_token}
    payload = {"media_id": media_id}
    resp = httpx.post(url, params=params, json=payload, timeout=30)
    data = resp.json()
    if data.get("errcode", 0) == 0:
        return data.get("publish_id", "")
    errcode = data.get("errcode", -1)
    errmsg = ERROR_CODES.get(errcode, data.get("errmsg", "未知错误"))
    raise RuntimeError(f"发布失败 [{errcode}]: {errmsg}")


def process_content_images(html_content: str, md_file_path: str,
                           access_token: str) -> str:
    """处理 HTML 中的本地图片：上传到微信CDN并替换 src

    Args:
        html_content: 包含图片标签的 HTML
        md_file_path: Markdown 文件路径（用于解析图片相对路径）
        access_token: 微信 access_token

    Returns:
        替换图片地址后的 HTML
    """
    md_dir = os.path.dirname(os.path.abspath(md_file_path))
    img_pattern = re.compile(r'<img\s+src="([^"]+)"')
    uploaded_cache = {}

    def replace_img(match):
        src = match.group(1)
        # 已经是网络地址，跳过
        if src.startswith(("http://", "https://")):
            return match.group(0)
        # 解析本地路径
        img_path = os.path.join(md_dir, src) if not os.path.isabs(src) else src
        img_path = os.path.normpath(img_path)
        if not os.path.exists(img_path):
            return match.group(0)
        # 使用缓存避免重复上传
        if img_path in uploaded_cache:
            cdn_url = uploaded_cache[img_path]
        else:
            cdn_url = upload_content_image(access_token, img_path)
            uploaded_cache[img_path] = cdn_url
        return f'<img src="{cdn_url}"'

    return img_pattern.sub(replace_img, html_content)


def find_first_image(md_content: str, md_file_path: str) -> Optional[str]:
    """从 Markdown 中找到第一张图片的本地路径"""
    md_dir = os.path.dirname(os.path.abspath(md_file_path))
    match = re.search(r'!\[[^\]]*\]\(([^)]+)\)', md_content)
    if not match:
        return None
    src = match.group(1)
    if src.startswith(("http://", "https://")):
        return None
    img_path = os.path.join(md_dir, src) if not os.path.isabs(src) else src
    img_path = os.path.normpath(img_path)
    return img_path if os.path.exists(img_path) else None


def extract_title(md_content: str) -> str:
    """从 Markdown 第一行 H1 提取标题"""
    for line in md_content.split('\n'):
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    return ""
