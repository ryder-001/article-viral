"""批量生图脚本：解析 md 中的 ![desc](prompt: ...) 标记，调用 DashScope 文生图，
下载到 imgs 目录并替换 md 中的图片路径。同时为每篇生成封面图。
"""
import os
import re
import sys
import time
import json
import httpx
from dotenv import dotenv_values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_DIR = os.path.join(ROOT, "data", "generated")
IMG_DIR = os.path.join(GEN_DIR, "2026-06-13-imgs")
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

PROMPT_RE = re.compile(r'!\[([^\]]*)\]\(prompt:\s*([^)]+)\)')


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

    matches = list(PROMPT_RE.finditer(content))
    print(f"\n=== {os.path.basename(md_path)} : {len(matches)} 张待生成正文配图 ===")

    # 已引用图片的最大序号，新图从其后接续，避免覆盖已生成的图
    existing = re.findall(re.escape(slug) + r"-(\d+)\.png", content)
    start_idx = max((int(x) for x in existing), default=0) + 1

    # 1. 正文配图
    new_content = content
    for i, m in enumerate(matches, start_idx):
        desc, prompt = m.group(1), m.group(2).strip()
        prompt_full = prompt if "no text" in prompt else prompt + ", no text"
        fname = f"{slug}-{i}.png"
        fpath = os.path.join(IMG_DIR, fname)
        rel = f"2026-06-13-imgs/{fname}"
        print(f"  [{i}] 生成中: {desc[:30]}...")
        try:
            tid = submit(prompt_full)
            url = poll(tid)
            if url:
                kb = download(url, fpath) // 1024
                print(f"      ✓ {fname} ({kb}KB)")
                new_content = new_content.replace(m.group(0), f"![{desc}]({rel})")
            else:
                print(f"      ✗ 生成失败，保留prompt标记")
        except Exception as e:
            print(f"      ✗ 异常: {e}")

    # 2. 封面图（用首图prompt衍生）
    cover_fname = f"{slug}-cover.png"
    cover_path = os.path.join(IMG_DIR, cover_fname)
    if matches:
        first_prompt = matches[0].group(2).strip()
    else:
        first_prompt = "a clean editorial illustration"
    cover_prompt = (first_prompt.replace(", no text", "") +
                    ", magazine cover style, eye-catching, high quality composition, no text")
    print(f"  [封面] {cover_size} 生成中...")
    try:
        tid = submit(cover_prompt, size=cover_size)
        url = poll(tid)
        if url:
            kb = download(url, cover_path) // 1024
            print(f"      ✓ {cover_fname} ({kb}KB)")
    except Exception as e:
        print(f"      ✗ 封面异常: {e}")

    if new_content != content:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("  → md 图片路径已替换")


# 文章清单: (文件名slug, 封面尺寸)  头条用宽图
ARTICLES = [
    ("世界杯观赛指南", "1440*608"),     # 头条 ≈2.35:1
    ("金价要不要买黄金", "1024*1024"),
    ("高考志愿填报3个坑", "1024*1024"),
    ("看懂配料表避开隐形糖", "1024*1024"),
    ("蜱虫叮咬别硬拔", "1024*1024"),
    ("识破AI生成人像", "1024*1024"),
    ("AI-Agent是什么", "1024*1024"),
]

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for slug, cover_size in ARTICLES:
        if only and only != slug:
            continue
        md_path = os.path.join(GEN_DIR, f"2026-06-13-{slug}.md")
        if not os.path.exists(md_path):
            print(f"跳过(不存在): {md_path}")
            continue
        process_file(md_path, slug, cover_size)
    print("\n全部完成")
