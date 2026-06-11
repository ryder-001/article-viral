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
# 采集各平台热榜
python3 -m scripts.cli hot

# 采集爆款文章
python3 -m scripts.cli collect "关键词" --platform toutiao

# AI检测文章
python3 -m scripts.cli detect article.md

# 发布到公众号（保存草稿）
python3 -m scripts.cli publish article.md

# 查看数据统计
python3 -m scripts.cli stats

# 查看/管理登录状态
python3 -m scripts.cli login
```

---

## 全自动流水线

1. 环境初始化（自动装依赖+浏览器）
2. 确保微信已登录
3. 热点采集（可选，用户没给主题时自动推荐）
4. 选题确定
5. 写文章（遵循爆文规则 + Anti-AI 写作）
6. AI 检测（≤40放行，41-70警告，>70阻断改写）
7. 配图（优先 AI 生图，失败用 Pillow 卡片）
8. 封面图（头条=2.35:1留白，非头条=1:1）
9. 发布（Playwright 自动化保存草稿）
10. 报告结果

---

## 要求

- Python 3.9+（macOS/Linux/Windows）
- 一个微信公众号（个人号就行）
