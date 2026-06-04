---
name: article-viral
description: "Use when the user wants to create viral WeChat public account articles, collect trending articles from multiple platforms, analyze viral writing patterns, generate high-engagement articles, or manage article generation rules. Triggers: '爆文', '爆款文章', '公众号文章', '采集文章', '生成文章', '写文章', '/article', 'viral article', 'trending content', '流量文'. Also triggers when user mentions collecting articles from WeChat, Toutiao, Baidu Baijiahao, Weibo, Sohu, or Zhihu for content creation purposes."
---

# 公众号爆款文章生成 Skill

从多平台采集爆款文章 → 分析写作规则 → 生成高传播力文章 → 积累经验迭代优化。

## Quick Reference

| 命令 | 用途 |
|------|------|
| `/article collect <关键词>` | 采集指定关键词的爆款文章 |
| `/article analyze` | 分析已采集文章，提取爆文规则 |
| `/article generate <主题>` | 基于规则生成爆款文章 |
| `/article rules` | 查看当前积累的爆文规则 |
| `/article` | 全流程：采集 → 分析 → 生成 |

## 自动初始化（每次执行前必须先运行）

在执行任何子命令前，先定位 skill 目录并运行 setup 脚本确保环境就绪。
setup.py 会自动完成：安装 Python 依赖、安装 Playwright Chromium 浏览器、创建数据目录、生成默认配置。
已安装过的组件会通过缓存跳过检测（7天内不重复），首次运行约需 1-2 分钟。

```bash
# 定位 skill 目录
SKILL_DIR="$(find "${SKILL_SEARCH_PATHS:-$HOME}" -type f -name "SKILL.md" -path "*/article-viral/*" -exec dirname {} \; 2>/dev/null | head -1)"
cd "$SKILL_DIR" && python3 scripts/setup.py
```

如果 setup.py 执行失败（网络问题等），可手动重试：
```bash
cd "$SKILL_DIR" && python3 -m pip install -q httpx beautifulsoup4 lxml pyyaml click playwright && python3 -m playwright install chromium
```

所有数据存储在 `$SKILL_DIR/data/` 下（自动创建），用户无需手动创建任何目录。

## collect 流程

```bash
python3 -m scripts.cli collect "<关键词>" --platform <平台> --max-results <数量>
```

注意：运行时需要先 cd 到 SKILL_DIR：
```bash
cd "$SKILL_DIR" && python3 -m scripts.cli collect "<关键词>"
```

支持平台：`wechat` `toutiao` `baijiahao` `weibo` `sohu` `zhihu`

## analyze 流程

1. 导出待分析文章：
```bash
cd "$SKILL_DIR" && python3 -m scripts.cli analyze --output data/temp_articles.json
```

2. 读取 `data/temp_articles.json`，对每篇文章进行**多维度深度分析**：

### 标题分析
- 字数、句式结构（陈述/疑问/感叹/对比）
- 情绪词和触发词识别
- 数字使用、悬念/对比手法
- 标题公式归纳（如"数字+方法+利益承诺"）

### 内容深度分析（核心）
- **开篇钩子**：前 100 字用什么手法抓住读者？（故事引入/反常识/痛点共鸣/数据震撼/提问式）
- **叙事结构**：全文采用什么逻辑推进？（问题→方案/现象→原因→对策/故事→感悟→行动）
- **节奏控制**：段落长度变化规律、长短句交替、密集信息与情感喘息的分布
- **案例密度**：每多少字出现一个案例/数据/故事？案例的来源类型（个人经历/名人故事/数据研究/身边人）
- **情感曲线**：全文情感走向（焦虑→安抚→信心/好奇→满足→行动）
- **金句分布**：高传播力句子的位置和密度（开头/转折处/结尾）
- **信息密度**：干货与故事的配比，是否每个观点都有支撑
- **口语化程度**：对话感句式占比、"你""我"人称使用频率
- **冲突与张力**：是否制造认知冲突、是否有转折和意外、是否有"颠覆常识"的观点
- **可操作性**：给出的建议/方法是否具体到"今天就能做"

### 结构分析
- 段落数、段落长度分布
- 小标题使用方式（数字型/问题型/金句型）
- 总分总 / 递进 / 并列等结构类型
- 首段钩子强度评分（1-5）

### 互动设计分析
- 评论引导方式和位置
- 结尾 CTA 类型（提问/征集/转发引导/预告）
- 文中是否埋设争议点引发站队

### 运营数据关联
- 将内容特征与阅读量/点赞/评论数关联，找出高互动文章的共性
- 对比同领域高低互动文章的差异点

3. 读取 `data/rules/global_rules.md`，将新发现的规律合并更新：
   - 如果发现新的内容模式，新增到对应章节
   - 如果某个规律被多篇文章验证，提升其权重/排序
   - 更新 "来源文章数" 计数器

4. 标记已分析：
```bash
cd "$SKILL_DIR" && python3 -m scripts.cli mark-analyzed <ids>
```

## generate 流程

1. 读取 `data/rules/global_rules.md`
2. 获取参考文章：
```bash
cd "$SKILL_DIR" && python3 -m scripts.cli analyze --limit 5
```
3. 生成要求：
   - 严格遵循规则中的标题/结构/内容/互动规则
   - 参考爆款风格但不抄袭
   - 完整公众号文章：标题 + 正文 + 结尾互动
   - 字数 800-1500 字
4. 保存到 `data/generated/YYYY-MM-DD-主题.md`
5. 展示结果供用户审阅

## rules 流程

1. 读取 `data/rules/` 下所有规则文件并展示
2. 统计：
```bash
cd "$SKILL_DIR" && python3 -m scripts.cli stats
```

## 全流程（无参数）

询问用户关键词和主题，依次执行 collect → analyze → generate。
