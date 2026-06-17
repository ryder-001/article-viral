# 多平台内容工具 (article-tools)

对 Claude 说"帮我写一篇关于XX的公众号文章"，自动完成全流程：

**热点采集 → 分析爆款规律 → 写文章 → AI检测 → 配图 → 封面图 → 发布到公众号草稿箱**

个人未认证订阅号可用，零配置。

---

## 安装

```bash
git clone https://github.com/ryder-001/article-viral.git ~/.claude/skills/article_tools
```

装好了。剩下的事 Claude 全部自动搞定（装依赖、装浏览器、登录）。

---

## 使用

在 Claude Code 里直接说：

- "帮我写一篇关于高考的公众号文章"
- "最近有什么热点？帮我写篇文章"
- "采集一些职场方向的爆款文章，分析规律"
- "采集一下各平台热榜"

第一次用会弹出浏览器让你扫码登录微信公众号后台，之后就不用了。

---

## CLI 命令

```bash
# 采集各平台热榜（知乎/微博/头条/百度）
python3 -m scripts.cli hot
python3 -m scripts.cli hot --platform weibo,baidu --limit 10

# 采集爆款文章（HTTP 搜索）
python3 -m scripts.cli collect "关键词" --platform toutiao
python3 -m scripts.cli collect "高考" --platform toutiao,wechat --max-results 10

# 深度采集全文（浏览器提取正文）
python3 -m scripts.cli deepcollect "URL1" "URL2" --platform toutiao
python3 -m scripts.cli deepcollect --keyword "职场" --limit 20

# 分析爆款规律，导出分析素材（触发规则迭代）
python3 -m scripts.cli update-rules --limit 30

# AI 检测文章
python3 -m scripts.cli detect article.md
python3 -m scripts.cli detect article.md --local-only --threshold 50

# 发布到公众号（默认保存草稿）
python3 -m scripts.cli publish article.md
python3 -m scripts.cli publish article.md --cover cover.png --theme blue
python3 -m scripts.cli publish article.md --html-only

# 生成上下文包（供手动分析）
python3 -m scripts.cli generate "主题" --ref-count 5

# 查看数据统计
python3 -m scripts.cli stats

# 登录管理
python3 -m scripts.cli login          # 查看状态
python3 -m scripts.cli login wechat   # 登录微信

# 查看爆文规则
python3 -m scripts.cli rules
python3 -m scripts.cli rules --name global_rules
```

---

## 核心闭环：规则迭代

```
collect（搜索文章）→ deepcollect（全文提取）→ update-rules（开放式分析）
→ 自动发现新规则维度 → 创建/更新规则文件 → 写文章时引用全部规则
```

规则不是预设的，而是从真实爆款全文中自动发现。每次采集新领域文章后运行 `update-rules`，规则体系会自然增长。

---

## 规则体系（分类目录）

```
data/rules/
├── writing/         # 写作技巧类
│   ├── global_rules.md           # 全局写作规则 v5
│   ├── opening_hook_rules.md     # 开篇钩子（4种模式）
│   ├── emotional_rhythm_rules.md # 情绪节奏（3种模式）
│   └── layout_rhythm_rules.md    # 排版节奏与视觉分层
├── style/           # 风格语言类
│   └── anti_ai_rules.md          # 去AI味写作规则
├── visual/          # 视觉配图类
│   └── visual_rules.md           # 配图与视觉规则
├── engagement/      # 互动传播类
│   └── shareability_rules.md     # 转发驱动（5种机制）
├── domain/          # 领域专属规则
│   ├── business_observation_rules.md  # 商业观察
│   ├── event_hotspot_rules.md         # 赛事热点
│   └── health_wellness_rules.md       # 健康养生
├── platform/        # 平台适配规则
│   └── toutiao_rules.md          # 头条平台特性
└── strategy/        # 运营策略类
    ├── content_strategy_rules.md  # 内容爆款策略
    └── sticker_operation_rules.md # 贴图运营
```

---

## 全自动流水线

| 步骤 | 说明 | 自动化程度 |
|------|------|-----------|
| 1. 环境初始化 | 自动装依赖 + Playwright Chromium | 全自动 |
| 2. 登录检查 | 检测 cookie 是否有效 | 需扫码时弹窗 |
| 3. 热点采集 | 浏览器抓取知乎/微博/头条/百度热榜 | 全自动 |
| 4. 选题确定 | 用户指定或从热榜推荐 | 交互 |
| 5. 写文章 | 读取全部规则 + Anti-AI 写作 | 全自动 |
| 6. AI 检测 | ≤10放行，11-70警告，>70阻断改写 | 全自动 |
| 7. 配图 | 优先 AI 生图，失败用 Pillow 卡片 | 全自动 |
| 8. 封面图 | 头条=2.35:1留白，非头条=1:1 | 全自动 |
| 9. 发布 | Playwright 自动化保存草稿 | 全自动 |
| 10. 报告 | 输出标题/字数/配图/AI检测结果 | 全自动 |

---

## 项目结构

```
article_tools/
├── SKILL.md                # Claude skill 定义（全自动流水线）
├── config.yaml             # 平台配置、阈值
├── data/
│   ├── rules/              # 规则文件（分类目录，动态生成）
│   ├── generated/          # 生成的文章和图片（gitignore）
│   ├── articles.db         # SQLite 数据库
│   └── cookies/            # 登录 cookie（gitignore）
└── scripts/
    ├── setup.py            # 环境初始化
    ├── cli.py              # CLI 入口（Click）
    ├── db.py               # 数据层（自动迁移旧库）
    ├── content_extractor.py # 浏览器全文提取（6平台+通用）
    ├── rule_analyzer.py    # 开放式规则分析器
    ├── rules.py            # 规则加载（递归扫描子目录）
    ├── hot_topics.py       # 热榜采集（4平台）
    ├── browser_fetcher.py  # 浏览器指标采集
    ├── login_manager.py    # 登录管理
    ├── ai_detector.py      # AI 痕迹检测
    ├── image_gen.py        # Pillow 卡片生成（fallback）
    ├── md_to_wechat.py     # Markdown → 微信排版HTML
    ├── publish.py          # 微信API发布
    ├── wechat_publisher.py # Playwright自动化发布
    └── collect/            # 多平台采集器
        ├── wechat.py       # 微信（搜狗点击跟踪）
        ├── toutiao.py      # 头条（HTTP）
        ├── baijiahao.py    # 百家号（百度资讯搜索）
        ├── weibo.py        # 微博
        ├── sohu.py         # 搜狐
        └── zhihu.py        # 知乎（API + HTML fallback）
```

---

## 多平台采集状态

| 平台 | 搜索方式 | 全文采集 | 状态 |
|------|---------|---------|------|
| 头条 | HTTP 搜索 | Playwright 提取 | ✅ 稳定 |
| 微信 | 搜狗点击跟踪 | Playwright 提取 | ✅ 可用 |
| 知乎 | Playwright + cookie | Playwright 提取 | ✅ 可用 |
| 百家号 | Playwright 百度资讯 | Playwright 提取 | ✅ 可用 |
| 微博 | 热榜正常 | Playwright 提取 | ✅ 热榜可用 |
| 百度 | 热榜正常 | — | ✅ 热榜可用 |

---

## 技术栈

- **Python 3.9+** — 主语言
- **Playwright** — 浏览器自动化（采集、登录、发布）
- **SQLite** — 文章/作者/生成记录存储
- **Click** — CLI 框架
- **httpx** — 异步 HTTP 采集
- **baoyu-image-gen** — AI 配图生成，命令行 `bun` 调用内置 `.agents/skills/baoyu-image-gen`（DashScope/OpenAI/Google 等）
- **Pillow** — 卡片式配图 fallback

---

## 要求

- Python 3.9+（macOS/Linux/Windows）
- 一个微信公众号（个人号就行）
