# 多平台内容工具 (article-tools)

对 Claude 说"帮我写一篇关于XX的公众号文章"，自动完成全流程：

**热点采集 → 写爆款文章 → AI检测 → 配图 → 封面图 → 发布到公众号草稿箱**

个人未认证订阅号可用，零配置。

---

## 安装

```bash
git clone https://github.com/ryder-001/article-viral.git ~/Documents/dev/code/51talk/article_tools
```

装好了。剩下的事 Claude 全部自动搞定（装依赖、装浏览器、登录）。

---

## 使用

在 Claude Code 里直接说：

- "帮我写一篇关于高考的公众号文章"
- "最近有什么热点？帮我写篇文章"
- "发一篇公众号文章，主题是职场焦虑"
- "采集一下各平台热榜"

第一次用会弹出浏览器让你扫码登录微信公众号后台，之后就不用了。

---

## CLI 命令

```bash
# 采集各平台热榜（知乎/微博/头条/百度）
python3 -m scripts.cli hot
python3 -m scripts.cli hot --platform weibo,baidu --limit 10

# 采集爆款文章
python3 -m scripts.cli collect "关键词" --platform toutiao
python3 -m scripts.cli collect "高考" --platform toutiao,wechat --max-results 10

# AI 检测文章
python3 -m scripts.cli detect article.md
python3 -m scripts.cli detect article.md --local-only --threshold 50

# 发布到公众号（默认保存草稿）
python3 -m scripts.cli publish article.md
python3 -m scripts.cli publish article.md --cover cover.png --theme blue
python3 -m scripts.cli publish article.md --html-only  # 仅生成HTML

# 生成上下文包（供手动分析）
python3 -m scripts.cli generate "主题" --ref-count 5

# 查看数据统计
python3 -m scripts.cli stats

# 登录管理
python3 -m scripts.cli login          # 查看状态
python3 -m scripts.cli login wechat   # 登录微信

# 查看作者数据
python3 -m scripts.cli authors --platform toutiao

# 查看爆文规则
python3 -m scripts.cli rules
python3 -m scripts.cli rules --name global_rules
```

---

## 全自动流水线

| 步骤 | 说明 | 自动化程度 |
|------|------|-----------|
| 1. 环境初始化 | 自动装依赖 + Playwright Chromium | 全自动 |
| 2. 登录检查 | 检测 cookie 是否有效 | 需扫码时弹窗 |
| 3. 热点采集 | 浏览器抓取知乎/微博/头条/百度热榜 | 全自动 |
| 4. 选题确定 | 用户指定或从热榜推荐 | 交互 |
| 5. 写文章 | 读取爆文规则 + Anti-AI 写作 | 全自动 |
| 6. AI 检测 | ≤40放行，41-70警告，>70阻断改写 | 全自动 |
| 7. 配图 | 优先 AI 生图，失败用 Pillow 卡片 | 全自动 |
| 8. 封面图 | 头条=2.35:1留白，非头条=1:1 | 全自动 |
| 9. 发布 | Playwright 自动化保存草稿 | 全自动 |
| 10. 报告 | 输出标题/字数/配图/AI检测结果 | 全自动 |

---

## 项目结构

```
article_tools/
├── SKILL.md              # Claude skill 定义（全自动流水线）
├── config.yaml           # 平台配置、阈值
├── data/
│   ├── rules/            # 爆文写作规则（v4，通用领域）
│   ├── generated/        # 生成的文章和图片（gitignore）
│   ├── articles.db       # SQLite 数据库
│   └── cookies/          # 登录 cookie（gitignore）
└── scripts/
    ├── setup.py          # 环境初始化
    ├── cli.py            # CLI 入口（Click）
    ├── db.py             # 数据层（自动迁移旧库）
    ├── hot_topics.py     # 热榜采集（4平台）
    ├── browser_fetcher.py # 浏览器指标采集
    ├── login_manager.py  # 登录管理
    ├── ai_detector.py    # AI 痕迹检测
    ├── image_gen.py      # Pillow 卡片生成（fallback）
    ├── md_to_wechat.py   # Markdown → 微信排版HTML
    ├── publish.py        # 微信API发布
    ├── rules.py          # 规则文件加载
    └── collect/          # 6平台采集器
        ├── wechat.py
        ├── toutiao.py
        ├── baijiahao.py
        ├── weibo.py
        ├── sohu.py
        └── zhihu.py
```

---

## 技术栈

- **Python 3.9+** — 主语言
- **Playwright** — 浏览器自动化（采集指标、登录、发布）
- **SQLite** — 文章/作者/生成记录存储
- **Click** — CLI 框架
- **httpx** — 异步 HTTP 采集
- **baoyu-image-gen** — AI 配图生成（DashScope/OpenAI/Google 等）
- **Pillow** — 卡片式配图 fallback

---

## 要求

- Python 3.9+（macOS/Linux/Windows）
- 一个微信公众号（个人号就行）
