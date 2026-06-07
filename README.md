# 公众号文章一键发布 (wechat-publish)

输入主题，AI 自动写爆款文章 + 配图 + 发布到公众号草稿箱。

**个人未认证订阅号可用，零配置开箱即用。**

## 安装（3步）

### 1. 克隆到 Claude Code skills 目录

```bash
git clone https://github.com/yourname/wechat-publish.git ~/.claude/skills/wechat-publish
```

### 2. 首次初始化（自动安装依赖）

```bash
cd ~/.claude/skills/wechat-publish && python3 scripts/setup.py
```

> 自动安装 Python 依赖 + Playwright 浏览器，约 1-2 分钟。

### 3. 登录微信公众号（扫码一次，后续免登）

```bash
cd ~/.claude/skills/wechat-publish && python3 -m scripts.cli login wechat
```

浏览器弹出后用微信扫码登录公众号后台，完成后 cookie 自动保存。

---

## 使用

在 Claude Code 中直接说：

```
帮我写一篇关于高考的公众号文章
```

或者：

```
写一篇关于暑假孩子自律的文章并发布到公众号
```

AI 会自动完成全流程，文章保存到草稿箱后提示你去后台确认发布。

---

## 手动命令

```bash
# 查看登录状态
python3 -m scripts.cli login

# 重新登录（cookie过期时）
python3 -m scripts.cli login wechat

# 手动发布已有的 Markdown 文件
python3 -m scripts.cli publish article.md

# 仅生成 HTML（不打开浏览器）
python3 -m scripts.cli publish article.md --html-only
```

## 原理

1. AI 根据内置爆文规则写 Markdown 文章
2. 用 Pillow 生成对比图/信息卡/金句卡等配图
3. Markdown → 微信排版 HTML（内联CSS + 自动选色）
4. 本地图片 → base64 嵌入 HTML
5. Playwright 打开公众号后台 → 填标题 → 粘贴正文 → 保存草稿

公众号编辑器会自动将 base64 图片上传到微信 CDN。

## 要求

- Python 3.9+
- macOS / Linux / Windows
- 一个微信公众号（个人号即可）
