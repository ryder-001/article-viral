"""规则加载模块 - 读取 data/rules/ 下所有规则文件并提供统一访问接口"""
import os
import glob
from typing import Optional


RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "rules"
)


def load_all_rules() -> dict:
    """加载所有规则文件，返回 {文件名: 内容} 字典"""
    rules = {}
    if not os.path.isdir(RULES_DIR):
        return rules
    for filepath in sorted(glob.glob(os.path.join(RULES_DIR, "*.md"))):
        name = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, "r", encoding="utf-8") as f:
            rules[name] = f.read()
    return rules


def load_rule(name: str) -> Optional[str]:
    """加载指定规则文件内容"""
    filepath = os.path.join(RULES_DIR, f"{name}.md")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return None


def get_rules_summary() -> str:
    """返回所有规则文件的摘要（文件名+版本行+字数）"""
    rules = load_all_rules()
    if not rules:
        return "暂无规则文件"
    lines = []
    for name, content in rules.items():
        # 提取版本行
        version_line = ""
        for line in content.split("\n"):
            if line.strip().startswith("> 版本"):
                version_line = line.strip().lstrip("> ")
                break
        char_count = len(content)
        lines.append(f"  {name}.md ({char_count}字) {version_line}")
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
