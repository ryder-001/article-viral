"""爆款规则分析器

分析采集到的爆款文章全文，提取写作规律，生成结构化分析结果。
供 Claude 读取后自动更新 data/rules/global_rules.md。
"""
import json
import os
from datetime import datetime
from typing import Optional
from scripts.db import ArticleDB


class RuleAnalyzer:
    """分析爆款文章，提取可操作的写作规律"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "articles.db"
            )
        self.db = ArticleDB(db_path)

    def get_articles_for_analysis(self, limit: int = 20,
                                  min_content_length: int = 300,
                                  platform: str = None) -> list[dict]:
        """获取有全文内容的爆款文章，供分析用"""
        if platform:
            rows = self.db.conn.execute(
                "SELECT * FROM articles "
                "WHERE is_viral = 1 AND length(content) > ? AND platform = ? "
                "ORDER BY read_count DESC LIMIT ?",
                (min_content_length, platform, limit)
            ).fetchall()
        else:
            rows = self.db.conn.execute(
                "SELECT * FROM articles "
                "WHERE is_viral = 1 AND length(content) > ? "
                "ORDER BY read_count DESC LIMIT ?",
                (min_content_length, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def prepare_analysis_context(self, articles: list[dict]) -> str:
        """将文章整理为分析上下文（供 AI 分析用）"""
        if not articles:
            return ""

        context_parts = []
        context_parts.append(f"# 爆款文章分析素材（共 {len(articles)} 篇）\n")
        context_parts.append(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        for i, art in enumerate(articles, 1):
            content_preview = art.get("content", "")[:2000]
            context_parts.append(f"\n---\n## 文章 {i}: {art.get('title', '无标题')}")
            context_parts.append(f"- 平台: {art.get('platform', '未知')}")
            context_parts.append(f"- 作者: {art.get('author', '未知')}")
            context_parts.append(
                f"- 阅读: {art.get('read_count', 0)} | "
                f"点赞: {art.get('like_count', 0)} | "
                f"评论: {art.get('comment_count', 0)}")
            context_parts.append(f"\n### 全文内容\n{content_preview}")
            if len(art.get("content", "")) > 2000:
                context_parts.append(f"\n...(原文共约{len(art['content'])}字)")

        return "\n".join(context_parts)

    def get_analysis_prompt(self) -> str:
        """返回分析提示词，供 Claude 直接使用

        核心设计：开放式发现机制，不预设固定维度。
        从文章内容本身涌现出新的规则类别。
        """
        # 读取现有规则文件列表作为参考
        existing_rules = self._get_existing_rule_names()
        existing_list = "\n".join(f"  - {name}" for name in existing_rules)

        return f"""请分析以上爆款文章，**开放式**提取所有可复用的写作规律。

## 分析原则

**不要局限于预设维度。** 从文章内容本身去发现规律——任何反复出现的模式、技巧、结构都值得提炼为规则。

已有规则文件（仅供参考，不是限制）：
{existing_list}

## 分析任务

### 第一步：发现规则维度

仔细阅读每篇文章，识别出所有可提炼为规则的**维度/类别**。每个维度应该是一个可独立成文件的规则主题。

可能的维度举例（仅作启发，请从文章中自行发现）：
- 标题公式规则
- 开篇钩子规则
- 叙事结构规则
- 数据引用规则
- 情绪节奏规则
- 口语化表达规则
- 排版节奏规则
- 互动引导规则
- 配图视觉规则
- 信息密度规则
- 权威引用规则
- 场景描写规则
- 案例构造规则
- 金句打造规则
- 转发驱动规则
- 领域专属规则（财经/职场/科技/教育/...）
- SEO/平台算法规则
- ...（任何你从文章中发现的新维度）

### 第二步：逐维度提取规律

对每个发现的维度，输出：

```markdown
## 规则维度：[维度名称]
建议文件名：[英文名]_rules.md
状态：[NEW-新发现 / UPDATE-更新已有 / CONFIRMED-验证已有]

### 规律描述
[具体的、可操作的规律描述]

### 证据（引用文章编号）
- 文章X：[具体例证]
- 文章Y：[具体例证]

### 可执行建议
[写文章时如何应用这条规律]
```

### 第三步：输出规则文件建议

最终给出建议：
1. 哪些是全新的规则文件（需要创建）
2. 哪些是对已有规则文件的补充（需要更新）
3. 每个规则文件的核心内容大纲

## 重要提醒

- 规则必须**具体、可操作**，不要泛泛而谈
- 每条规律必须有原文证据支撑
- 发现的维度数量不设上限——文章里有多少种规律就提取多少种
- 注意不同话题领域可能有各自独特的规律（这些也应该被提取）
- 如果某个规律只在1篇文章中出现，标注为"待验证"
- 如果某个规律在3篇以上文章中反复出现，标注为"高置信度"
"""

    def _get_existing_rule_names(self) -> list[str]:
        """获取现有规则文件名列表"""
        import glob as glob_mod
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "rules"
        )
        if not os.path.isdir(rules_dir):
            return []
        files = sorted(glob_mod.glob(os.path.join(rules_dir, "*.md")))
        return [os.path.splitext(os.path.basename(f))[0] for f in files]

    def export_for_analysis(self, limit: int = 20,
                            platform: str = None,
                            output_path: str = None) -> str:
        """导出分析素材到文件，返回文件路径"""
        articles = self.get_articles_for_analysis(
            limit=limit, platform=platform)

        if not articles:
            return ""

        context = self.prepare_analysis_context(articles)
        prompt = self.get_analysis_prompt()
        full_content = context + "\n\n---\n\n" + prompt

        if not output_path:
            output_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        return output_path

    def get_stats(self) -> dict:
        """获取当前可分析的数据统计"""
        total = self.db.conn.execute(
            "SELECT COUNT(*) FROM articles WHERE is_viral = 1"
        ).fetchone()[0]
        with_content = self.db.conn.execute(
            "SELECT COUNT(*) FROM articles "
            "WHERE is_viral = 1 AND length(content) > 300"
        ).fetchone()[0]
        platforms = self.db.conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM articles "
            "WHERE is_viral = 1 AND length(content) > 300 "
            "GROUP BY platform ORDER BY cnt DESC"
        ).fetchall()

        return {
            "total_viral": total,
            "with_full_content": with_content,
            "by_platform": {r[0]: r[1] for r in platforms},
            "ready_for_analysis": with_content >= 5,
        }

    def close(self):
        self.db.close()
