"""自动初始化环境 - 检测依赖、创建目录、初始化配置"""
import subprocess
import sys
import os

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED_PACKAGES = ["httpx", "beautifulsoup4", "lxml", "pyyaml", "click"]


def check_and_install_deps():
    """检查并自动安装缺失的依赖"""
    missing = []
    import_map = {
        "httpx": "httpx",
        "beautifulsoup4": "bs4",
        "lxml": "lxml",
        "pyyaml": "yaml",
        "click": "click",
    }
    for pkg, module in import_map.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[setup] 安装缺失依赖: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q"] + missing
        )
        print("[setup] 依赖安装完成")
    else:
        print("[setup] 依赖已就绪")


def init_directories():
    """创建必要的数据目录"""
    dirs = [
        os.path.join(SKILL_DIR, "data", "rules"),
        os.path.join(SKILL_DIR, "data", "generated"),
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

> 版本: v1 | 更新时间: 2026-06-03 | 来源文章数: 0

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
        print(f"[setup] 已创建初始规则文件")


def main():
    print("[setup] 正在初始化公众号爆文 skill 环境...")
    check_and_install_deps()
    init_directories()
    init_config()
    init_rules()
    print("[setup] 初始化完成！")


if __name__ == "__main__":
    main()
