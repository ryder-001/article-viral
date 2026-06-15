"""批量生图脚本 0614：解析 md 中已有路径的图片标记
![中文描述](2026-06-14-imgs/xxx.png)，用中文描述作为生图提示词，
调用 DashScope 文生图，下载到 2026-06-14-imgs 目录（图片不存在时才生成）。
同时为每篇生成封面图。
"""
import os
import re
import sys
import time
import httpx
from dotenv import dotenv_values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_DIR = os.path.join(ROOT, "data", "generated")
IMG_SUBDIR = "2026-06-14-imgs"
IMG_DIR = os.path.join(GEN_DIR, IMG_SUBDIR)
os.makedirs(IMG_DIR, exist_ok=True)

cfg = dotenv_values(os.path.join(ROOT, ".baoyu-skills", ".env"))
KEY = cfg.get("DASHSCOPE_API_KEY", "").strip()
CREATE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{}"
MODEL = "wanx2.1-t2i-turbo"

HEADERS_ASYNC = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "X-DashScope-Async": "enable",
}
HEADERS = {"Authorization": f"Bearer {KEY}"}

# 匹配本仓库当天图片：![描述](2026-06-14-imgs/文件名.png)
IMG_RE = re.compile(
    r'!\[([^\]]*)\]\((' + re.escape(IMG_SUBDIR) + r'/([^)]+\.png))\)'
)


def submit(prompt, size="1024*1024"):
    payload = {
        "model": MODEL,
        "input": {"prompt": prompt},
        "parameters": {"size": size, "n": 1},
    }
    r = httpx.post(CREATE_URL, headers=HEADERS_ASYNC, json=payload, timeout=40)
    r.raise_for_status()
    return r.json()["output"]["task_id"]


def poll(task_id, timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        r = httpx.get(TASK_URL.format(task_id), headers=HEADERS, timeout=40)
        data = r.json()["output"]
        st = data.get("task_status")
        if st == "SUCCEEDED":
            results = data.get("results", [])
            if results and results[0].get("url"):
                return results[0]["url"]
            return None
        if st in ("FAILED", "CANCELED", "UNKNOWN"):
            print(f"    任务失败: {st} {data.get('message','')}")
            return None
        time.sleep(4)
    print("    轮询超时")
    return None


def download(url, path):
    r = httpx.get(url, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    return os.path.getsize(path)


def process_file(md_path, slug, cover_size):
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    matches = list(IMG_RE.finditer(content))
    print(f"\n=== {os.path.basename(md_path)} : {len(matches)} 张配图 ===")

    first_desc = None
    for m in matches:
        desc, rel, fname = m.group(1), m.group(2), m.group(3)
        if first_desc is None:
            first_desc = desc
        fpath = os.path.join(IMG_DIR, fname)
        if os.path.exists(fpath):
            print(f"  [跳过] 已存在: {fname}")
            continue
        prompt_full = desc + ", no text, 高质量"
        print(f"  [生成] {desc[:30]}...")
        try:
            tid = submit(prompt_full)
            url = poll(tid)
            if url:
                kb = download(url, fpath) // 1024
                print(f"      ✓ {fname} ({kb}KB)")
            else:
                print(f"      ✗ 生成失败")
        except Exception as e:
            print(f"      ✗ 异常: {e}")

    # 封面图（用首图描述衍生）
    cover_fname = f"{slug}-cover.png"
    cover_path = os.path.join(IMG_DIR, cover_fname)
    if os.path.exists(cover_path):
        print(f"  [封面] 已存在，跳过")
        return
    base = first_desc or "一张干净的编辑风格插画"
    cover_prompt = base + ", magazine cover style, eye-catching, no text, 高质量"
    print(f"  [封面] {cover_size} 生成中...")
    try:
        tid = submit(cover_prompt, size=cover_size)
        url = poll(tid)
        if url:
            kb = download(url, cover_path) // 1024
            print(f"      ✓ {cover_fname} ({kb}KB)")
    except Exception as e:
        print(f"      ✗ 封面异常: {e}")


# (slug, 封面尺寸)  世界杯类用宽图利于头条
ARTICLES = [
    ("专业名字唬人", "1024*1024"),
    ("高考后防骗", "1024*1024"),
    ("看懂位次", "1024*1024"),
    ("世界杯失控", "1440*608"),
    ("世界杯饭桌接话", "1440*608"),
    ("旧金饰换新", "1024*1024"),
    ("识破稳赚骗局", "1024*1024"),
]

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for slug, cover_size in ARTICLES:
        if only and only != slug:
            continue
        md_path = os.path.join(GEN_DIR, f"2026-06-14-{slug}.md")
        if not os.path.exists(md_path):
            print(f"跳过(不存在): {md_path}")
            continue
        process_file(md_path, slug, cover_size)
    print("\n全部完成")
