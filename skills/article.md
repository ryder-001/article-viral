---
name: article
description: 公众号爆款文章自动采集、分析和生成。支持子命令：collect（采集）、analyze（分析）、generate（生成）、rules（查看规则）。无参数执行全流程。
---

# 公众号爆款文章 Skill

根据用户输入的参数确定执行哪个子命令：
- `collect [关键词]` → 执行采集流程
- `analyze` → 执行分析流程
- `generate [主题]` → 执行生成流程
- `rules` → 查看当前规则
- 无参数 → 交互式确定关键词和主题后执行全流程

## collect 流程

1. 运行采集脚本：
```bash
python -m scripts.cli collect "<关键词>"
```
2. 报告采集结果（采集了多少篇文章、来自哪些平台）

## analyze 流程

1. 导出待分析文章：
```bash
python -m scripts.cli analyze --output data/temp_articles.json
```
2. 读取 `data/temp_articles.json` 中的文章数据
3. 对每篇文章分析其爆款特征：
   - 标题特征：字数、句式、情绪词、数字使用、悬念/对比手法
   - 结构特征：段落数、段落长度、首段是否有钩子
   - 内容特征：故事性、数据引用、情感共鸣点
   - 互动特征：引导评论手法、结尾 CTA
4. 读取现有规则文件 `data/rules/global_rules.md`
5. 将新发现的规则与现有规则合并，更新规则文件
6. 标记已分析的文章：
```bash
python -m scripts.cli mark-analyzed <ids>
```

## generate 流程

1. 读取规则文件 `data/rules/global_rules.md`
2. 获取参考爆款文章：
```bash
python -m scripts.cli analyze --limit 5
```
3. 基于规则 + 参考文章，为用户指定的主题生成一篇爆款文章：
   - 严格遵循规则中的标题/结构/内容/互动规则
   - 参考爆款文章的风格但绝不抄袭
   - 生成完整公众号文章（标题 + 正文 + 结尾互动）
   - 字数控制在 800-1500 字
4. 将文章保存到 `data/generated/` 目录（文件名格式：YYYY-MM-DD-主题.md）
5. 展示生成结果供用户审阅和修改

## rules 流程

1. 读取 `data/rules/` 目录下所有规则文件并展示
2. 运行统计：
```bash
python -m scripts.cli stats
```

## 全流程（无参数）

询问用户关键词和主题，然后依次执行 collect → analyze → generate。
