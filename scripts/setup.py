"""自动初始化环境 - 检测依赖、安装浏览器、创建目录、初始化配置

运行时自动检测所有缺失组件并修复，用户无需手动干预。
支持：Python 依赖 / Playwright 浏览器 / 数据目录 / 默认配置
"""
import subprocess
import sys
import os
import shutil

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# pip 包名 -> import 模块名
REQUIRED_PACKAGES = {
    "httpx": "httpx",
    "beautifulsoup4": "bs4",
    "lxml": "lxml",
    "pyyaml": "yaml",
    "click": "click",
    "playwright": "playwright",
}

# 标记文件，避免每次都重复检测浏览器
_BROWSER_READY_FLAG = os.path.join(SKILL_DIR, "data", ".browser_ready")


def _run(cmd, check=True):
    """执行子进程命令"""
    try:
        return subprocess.run(
            cmd, check=check, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[setup] 命令失败: {' '.join(cmd)}")
        if e.stderr:
            for line in e.stderr.strip().split("\n")[:5]:
                print(f"        {line}")
        if check:
            raise
        return e


def check_and_install_deps():
    """检查并自动安装缺失的 Python 依赖"""
    missing = []
    for pkg, module in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[setup] 安装缺失依赖: {', '.join(missing)}")
        _run([sys.executable, "-m", "pip", "install", "-q"] + missing)
        print("[setup] Python 依赖安装完成")
    else:
        print("[setup] Python 依赖已就绪")


def check_and_install_browser():
    """检测 Playwright Chromium 浏览器是否已安装，未安装则自动安装"""
    # 如果标记文件存在且不超过 7 天，跳过检测
    if os.path.exists(_BROWSER_READY_FLAG):
        import time
        age = time.time() - os.path.getmtime(_BROWSER_READY_FLAG)
        if age < 7 * 86400:
            print("[setup] 浏览器已就绪（缓存）")
            return True

    # 检测 chromium 是否已下载
    try:
        result = _run(
            [sys.executable, "-m", "playwright", "install", "--dry-run",
             "chromium"], check=False
        )
        # dry-run 不存在时会直接安装，用 which 检测更可靠
        # 改用尝试导入并检查浏览器路径
        from playwright._impl._driver import compute_driver_executable
        driver = compute_driver_executable()
        if os.path.exists(driver):
            # 进一步验证 chromium 可执行文件
            result = _run(
                [sys.executable, "-c",
                 "from playwright.sync_api import sync_playwright;"
                 "p=sync_playwright().start();"
                 "b=p.chromium.executable_path;"
                 "print(b);p.stop()"],
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                browser_path = result.stdout.strip()
                if os.path.exists(browser_path):
                    _mark_browser_ready()
                    print("[setup] 浏览器已就绪")
                    return True
    except Exception:
        pass

    # 安装 chromium（含系统依赖）
    print("[setup] 正在安装 Chromium 浏览器（首次约 100-200MB）...")
    try:
        _run([sys.executable, "-m", "playwright", "install", "chromium"])
        # macOS/Windows 不需要 install-deps，Linux 需要
        if sys.platform == "linux":
            print("[setup] 安装系统依赖...")
            _run([sys.executable, "-m", "playwright", "install-deps",
                  "chromium"], check=False)
        _mark_browser_ready()
        print("[setup] Chromium 安装完成")
        return True
    except Exception as e:
        print(f"[setup] 浏览器安装失败: {e}")
        print("[setup] 提示: 可手动运行 python3 -m playwright install chromium")
        return False


def _mark_browser_ready():
    """写入标记文件"""
    os.makedirs(os.path.dirname(_BROWSER_READY_FLAG), exist_ok=True)
    with open(_BROWSER_READY_FLAG, "w") as f:
        f.write("ok")


def init_directories():
    """创建必要的数据目录"""
    dirs = [
        os.path.join(SKILL_DIR, "data", "rules"),
        os.path.join(SKILL_DIR, "data", "generated"),
        os.path.join(SKILL_DIR, "data", "cookies"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def init_config():
    """如果不存在则创建默认配置"""
    config_path = os.path.join(SKILL_DIR, "config.yaml")
    if not os.path.exists(config_path):
        default_config = """domain: "通用"
keywords:
  - "热门话题"

platforms:
  wechat: true
  toutiao: true
  baijiahao: true
  weibo: true
  sohu: true
  zhihu: true

collect:
  max_articles_per_platform: 20
  request_delay: [2, 5]
  user_agents: []
  proxy: ""

viral_threshold:
  wechat_likes: 1000
  toutiao_comments: 500
  weibo_reposts: 1000
  zhihu_upvotes: 1000
  default_reads: 100000

generate:
  min_words: 800
  max_words: 1500
  style: "通俗易懂，有故事性"
"""
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(default_config)
        print(f"[setup] 已创建默认配置: {config_path}")


def init_rules():
    """如果不存在则创建初始规则文件"""
    rules_path = os.path.join(SKILL_DIR, "data", "rules", "global_rules.md")
    if not os.path.exists(rules_path):
        default_rules = """# 爆文规则 - 通用

> 版本: v1 | 更新时间: 自动生成 | 来源文章数: 0

## 标题规则
- 控制在 15-25 字之间
- 使用数字增加具体感（如"3个方法"、"5分钟学会"）
- 制造信息差（"原来…"、"竟然…"）
- 对比式标题点击率高（A vs B、以前 vs 现在）
- 使用疑问句引发好奇（"为什么…？"）

## 结构规则
- 首段必须在 3 句话内制造悬念或引发共鸣
- 全文 800-1500 字为最佳阅读区间
- 使用小标题分割段落，每段不超过 150 字
- 关键信息加粗标记重点
- 结尾设置互动引导（提问、投票、征集评论）

## 内容规则
- 开头用故事、数据或反常识观点切入
- 每 200-300 字插入一个案例、数据或金句
- 使用口语化表达，像朋友聊天
- 制造"获得感"——读者读完觉得学到了东西
- 适当制造争议性，引发评论和转发

## 互动规则
- 文末设置开放式问题引导评论
- 使用"你觉得呢？""你有类似经历吗？"等话术
- 在文中埋设讨论点，让读者有参与感
"""
        with open(rules_path, "w", encoding="utf-8") as f:
            f.write(default_rules)
        print("[setup] 已创建初始规则文件")


def main():
    print("[setup] 正在初始化公众号爆文工具环境...")
    check_and_install_deps()
    check_and_install_browser()
    init_directories()
    init_config()
    init_rules()
    print("[setup] 初始化完成！所有组件就绪。")


if __name__ == "__main__":
    main()
