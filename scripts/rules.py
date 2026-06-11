"""规则加载模块 - 读取 data/rules/ 下所有规则文件（支持子目录分类）并提供统一访问接口"""
import os
import glob as glob_mod
from typing import Optional


RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "rules"
)

# 规则分类目录说明
RULE_CATEGORIES = {
    "writing": "写作技巧类（标题、开篇、结构、叙事等）",
    "style": "风格语言类（去AI味、语气、节奏等）",
    "visual": "视觉配图类（插图、封面、排版等）",
    "engagement": "互动传播类（评论引导、转发驱动等）",
    "domain": "领域专属规则（财经、科技、职场、教育等）",
    "platform": "平台适配规则（微信、头条、知乎等）",
    "strategy": "运营策略类（内容策略、贴图运营等）",
}


def load_all_rules() -> dict:
    """加载所有规则文件（递归扫描子目录），返回 {相对路径: 内容} 字典"""
    rules = {}
    if not os.path.isdir(RULES_DIR):
        return rules
    for filepath in sorted(glob_mod.glob(os.path.join(RULES_DIR, "**", "*.md"), recursive=True)):
        # 用相对于 RULES_DIR 的路径作为 key（如 "writing/global_rules"）
        rel_path = os.path.relpath(filepath, RULES_DIR)
        name = os.path.splitext(rel_path)[0]
        with open(filepath, "r", encoding="utf-8") as f:
            rules[name] = f.read()
    return rules


def load_rule(name: str) -> Optional[str]:
    """加载指定规则文件内容，支持带路径（如 'writing/global_rules'）或纯文件名"""
    # 先尝试直接匹配
    filepath = os.path.join(RULES_DIR, f"{name}.md")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    # 递归搜索
    for found in glob_mod.glob(os.path.join(RULES_DIR, "**", f"{name}.md"), recursive=True):
        with open(found, "r", encoding="utf-8") as f:
            return f.read()
    return None


def get_rules_summary() -> str:
    """返回所有规则文件的摘要（分类+文件名+版本行+字数）"""
    rules = load_all_rules()
    if not rules:
        return "暂无规则文件"

    # 按分类分组
    categorized = {}
    for name, content in rules.items():
        parts = name.split("/")
        category = parts[0] if len(parts) > 1 else "未分类"
        filename = parts[-1] if len(parts) > 1 else parts[0]
        if category not in categorized:
            categorized[category] = []
        # 提取版本行
        version_line = ""
        for line in content.split("\n"):
            if line.strip().startswith("> 版本") or line.strip().startswith("> 版本"):
                version_line = line.strip().lstrip("> ")
                break
        char_count = len(content)
        categorized[category].append(
            f"    {filename}.md ({char_count}字) {version_line}")

    lines = []
    for cat, items in sorted(categorized.items()):
        cat_desc = RULE_CATEGORIES.get(cat, "")
        lines.append(f"  [{cat}] {cat_desc}")
        lines.extend(items)
        lines.append("")
    return "\n".join(lines)


def get_combined_rules() -> str:
    """合并所有规则为单一文本，用于喂给 AI 生成"""
    rules = load_all_rules()
    if not rules:
        return ""
    parts = []
    for name, content in rules.items():
        parts.append(f"{'='*60}\n## 规则文件: {name}\n{'='*60}\n\n{content}")
    return "\n\n".join(parts)


def list_categories() -> dict:
    """列出所有规则分类及其包含的文件数量"""
    result = {}
    if not os.path.isdir(RULES_DIR):
        return result
    for cat in sorted(os.listdir(RULES_DIR)):
        cat_path = os.path.join(RULES_DIR, cat)
        if os.path.isdir(cat_path):
            files = glob_mod.glob(os.path.join(cat_path, "*.md"))
            result[cat] = {
                "description": RULE_CATEGORIES.get(cat, ""),
                "count": len(files),
                "files": [os.path.splitext(os.path.basename(f))[0] for f in sorted(files)],
            }
    return result
