# 公众号爆款文章自动生成 Skill 设计

## 概述

实现一个 Claude Code Skill，用于自动采集各平台爆款文章、分析提取写作规则、生成爆款文章，并持续积累生成经验。

## 目标

- 从微信公众号、今日头条、百家号、微博、搜狐、知乎采集爆款文章
- 分析爆款文章特征，提取可复用的写作规则
- 基于规则生成高质量爆款文章
- 持续积累和迭代生成经验

## 架构

### 目录结构

```
article_tools/
├── skills/
│   └── article.md              # 主 Skill 文件
├── scripts/
│   ├── collect/                 # 采集模块
│   │   ├── __init__.py
│   │   ├── base.py             # 采集器基类
│   │   ├── wechat.py           # 微信公众号（搜狗微信搜索）
│   │   ├── toutiao.py          # 今日头条
│   │   ├── baijiahao.py        # 百家号
│   │   ├── weibo.py            # 微博
│   │   ├── sohu.py             # 搜狐
│   │   └── zhihu.py            # 知乎
│   ├── analyze.py              # 分析模块
│   ├── db.py                   # SQLite 数据层
│   └── cli.py                  # 命令行入口
├── data/
│   ├── rules/                   # 爆文规则（Markdown）
│   │   ├── global_rules.md     # 通用爆文规则
│   │   └── {domain}_rules.md   # 领域专属规则
│   ├── articles.db             # SQLite 数据库
│   └── generated/              # 生成的文章输出
├── config.yaml                  # 配置文件
└── requirements.txt
```

### 数据流

```
采集(collect) → 存储(SQLite) → 分析(analyze) → 规则(rules/*.md) → 生成(Claude)
                                                         ↑
                                                    经验反馈循环
```

### Skill 子命令

- `/article collect [领域] [关键词]` — 采集指定领域的爆款文章
- `/article analyze` — 分析已采集文章，提取/更新爆文规则
- `/article generate [主题]` — 基于规则生成爆款文章
- `/article rules` — 查看当前积累的爆文规则
- `/article`（无参数）— 全流程：采集 → 分析 → 生成

## 模块详细设计

### 1. 采集模块 (scripts/collect/)

**基类 `BaseCollector`：**
- `search(keyword, domain)` — 搜索指定关键词的文章列表
- `fetch_article(url)` — 抓取单篇文章完整内容
- `get_metrics(article)` — 获取文章指标（阅读量、点赞、评论等）
- `is_viral(article)` — 判断是否为爆款（基于阅读量/互动率阈值）

**各平台采集策略：**

| 平台 | 入口方式 | 爆款判定 |
|------|---------|---------|
| 微信公众号 | 搜狗微信搜索 / 微信搜一搜 | 在看数 > 1000 或 10w+ |
| 今日头条 | 头条搜索 / 热榜 | 评论 > 500 |
| 百家号 | 百度搜索筛选 | 推荐量/阅读量比 |
| 微博 | 热搜/超话/搜索 | 转发 > 1000 |
| 搜狐 | 搜狐号搜索 | 阅读量 > 10w |
| 知乎 | 热榜/搜索 | 赞同 > 1000 |

**反爬处理：**
- 随机 User-Agent 轮换
- 请求间隔随机延迟（2-5s）
- Cookie 池管理（可选）
- 代理 IP 支持（可选，通过 config.yaml 配置）

### 2. 数据存储 (scripts/db.py)

**SQLite 表结构：**

```sql
-- 采集的文章
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,        -- 来源平台
    url TEXT UNIQUE,               -- 原文链接
    title TEXT NOT NULL,           -- 标题
    content TEXT,                  -- 正文内容
    author TEXT,                   -- 作者
    domain TEXT,                   -- 所属领域
    publish_time TEXT,             -- 发布时间
    collect_time TEXT,             -- 采集时间
    read_count INTEGER,            -- 阅读量
    like_count INTEGER,            -- 点赞数
    comment_count INTEGER,         -- 评论数
    share_count INTEGER,           -- 分享/转发数
    is_viral BOOLEAN DEFAULT 0,    -- 是否爆款
    analyzed BOOLEAN DEFAULT 0     -- 是否已分析
);

-- 生成记录
CREATE TABLE generated (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    domain TEXT,
    topic TEXT,
    rules_version TEXT,            -- 使用的规则版本
    generate_time TEXT,
    source_articles TEXT           -- 参考的爆款文章ID列表(JSON)
);
```

### 3. 分析模块 (scripts/analyze.py)

**分析维度：**
- 标题特征：字数、句式、情绪词、数字使用、悬念/对比手法
- 结构特征：段落数、段落长度、小标题使用、首段钩子
- 内容特征：故事性、数据引用、情感共鸣点、争议性话题
- 互动特征：引导评论的手法、结尾 CTA

**输出格式（写入 rules/*.md）：**
```markdown
# 爆文规则 - {领域}

## 标题规则
- 控制在 15-25 字
- 使用数字开头（如"3个方法"）效果好
- 对比式标题（A vs B）点击率高
...

## 结构规则
- 首段必须制造悬念或共鸣
- 全文 800-1500 字最佳
...

## 内容规则
- 每 200 字插入一个案例/故事
...
```

### 4. 经验积累系统

**积累方式：**
- 每次分析后更新 `data/rules/` 下对应领域的规则文件
- 规则文件采用追加 + 合并策略：新规则追加，重复规则合并并标注置信度
- 记录每条规则的来源文章数量，文章数越多的规则置信度越高
- 生成文章后可手动标记效果（好/差），反馈到规则权重

**规则版本管理：**
- 每次更新规则文件时在文件头部记录版本号和更新时间
- 生成文章时记录使用的规则版本，方便回溯

### 5. 配置文件 (config.yaml)

```yaml
# 领域配置
domain: "通用"
keywords:
  - "热门话题"

# 平台开关
platforms:
  wechat: true
  toutiao: true
  baijiahao: true
  weibo: true
  sohu: true
  zhihu: true

# 采集参数
collect:
  max_articles_per_platform: 20
  request_delay: [2, 5]  # 随机延迟范围（秒）
  user_agents: []         # 自定义 UA 列表，空则用默认
  proxy: ""               # 代理地址，空则不用

# 爆款阈值
viral_threshold:
  wechat_likes: 1000
  toutiao_comments: 500
  weibo_reposts: 1000
  zhihu_upvotes: 1000
  default_reads: 100000

# 生成参数
generate:
  min_words: 800
  max_words: 1500
  style: "通俗易懂，有故事性"
```

## 技术选型

- **Python 3.10+**
- **HTTP 请求**: httpx（支持异步）
- **HTML 解析**: beautifulsoup4 + lxml
- **数据库**: sqlite3（标准库）
- **配置**: pyyaml
- **CLI**: click

## Skill 工作流程

### `/article collect` 流程
1. 读取 config.yaml 获取领域和关键词
2. 并发调用各平台采集器搜索文章列表
3. 筛选爆款文章（根据阈值）
4. 抓取文章全文内容
5. 存入 SQLite 数据库

### `/article analyze` 流程
1. 从 SQLite 读取未分析的爆款文章
2. Claude 分析文章的标题/结构/内容/互动特征
3. 与已有规则合并，更新规则文件
4. 标记文章为已分析

### `/article generate [主题]` 流程
1. 读取对应领域的规则文件
2. 从 SQLite 选取几篇高质量爆款作为参考
3. Claude 基于规则 + 参考文章生成新文章
4. 输出到 data/generated/ 目录
5. 记录生成记录到 SQLite

### `/article rules` 流程
1. 读取并展示当前规则文件内容
2. 显示规则统计（条目数、来源文章数、最后更新时间）
