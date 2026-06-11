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
        """返回分析提示词，供 Claude 直接使用"""
        return """请分析以上爆款文章，从以下维度提取可复用的写作规律：

## 分析维度

### 1. 标题模式
- 提取标题公式（对比转折、数字列表、痛点否定、权威背书等）
- 统计标题长度分布
- 识别高频情绪触发词
- 标记标题中的标点使用模式

### 2. 开篇钩子
- 归类开篇类型（反常识、痛点共鸣、故事引入、数据震撼）
- 统计首段字数和句数
- 提取有效的开篇句式模板

### 3. 结构模式
- 正文分段方式（H2数量、段落长度分布）
- 叙事结构类型（问题→方案、故事→感悟、现象→真相）
- 案例/数据的插入频率和位置

### 4. 语言风格
- 口语化程度（"你""我"使用频率，口语连接词）
- 句长分布（长短句交替模式）
- 情感密度（情绪词分布）

### 5. 互动设计
- 结尾互动话术模板
- 文中埋设的讨论点
- 转发引导方式

### 6. 平台差异
- 不同平台的爆文风格差异
- 各平台读者偏好的内容类型

## 输出格式

以 Markdown 格式输出，结构与 data/rules/global_rules.md 对齐。
对于新发现的规律，标注 [NEW]；对于验证了已有规则的，标注 [CONFIRMED]。
给出具体的规律描述+原文例证（引用文章编号）。
"""

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
