---
name: article-viral
description: "一键生成公众号爆款文章并自动发布到微信公众号编辑器。输入主题即可完成全流程：AI写爆款文章 + 自动配图 + Playwright自动化粘贴到公众号后台编辑器 + 自动保存草稿。零配置开箱即用，个人未认证订阅号可用。触发词: '发公众号', '写公众号文章', '公众号发布', '发布文章', '写一篇文章发到公众号', '帮我发一篇', '写篇文章并发布', '/publish', '一键发布', '自动发布公众号', '生成并发布文章', '公众号一键发文', '帮我写篇公众号文章', '爆文', '爆款文章', '/article', '采集文章', '生成文章', '流量文'"
---

# 公众号文章一键发布

用户只需说出主题，你（Claude）自动完成所有步骤。用户不需要执行任何命令。

---

## Step 1: 初始化环境

自动执行，对用户透明：

```bash
cd ~/.claude/skills/article-viral && python3 scripts/setup.py
```

若失败则执行备用：
```bash
cd ~/.claude/skills/article-viral && python3 -m pip install -q httpx beautifulsoup4 lxml pyyaml click playwright pillow && python3 -m playwright install chromium
```

---

## Step 2: 确保微信已登录

```bash
cd ~/.claude/skills/article-viral && python3 -m scripts.cli login
```

- wechat 显示 `✓ 已登录` → 继续
- wechat 显示 `✗ 未登录` → 告诉用户"需要扫码登录微信公众号，马上弹出浏览器"，然后执行：

```bash
cd ~/.claude/skills/article-viral && python3 -m scripts.cli login wechat
```

---

## Step 3: 写文章 + 生成配图

### 3.1 读取规则

读取 `~/.claude/skills/article-viral/data/rules/global_rules.md`

### 3.2 写文章（Markdown）

根据用户主题 + 规则，生成完整文章：

| 要素 | 要求 |
|------|------|
| 标题 | H1，18-30字，数字+情绪触发+具体承诺 |
| 开篇 | 3句内抓注意力（反常识/痛点/故事） |
| 正文 | 800-1500字，3-4个H2小标题，每段配案例 |
| 结尾 | 金句+开放式问题+转发引导 |
| 风格 | 口语化，像朋友聊天，多用"你""我" |
| 配图 | 用 `![描述](images/子目录/文件名.jpg)` 标记 |

### 3.3 生成配图

```bash
cd ~/.claude/skills/article-viral && python3 -c "
from scripts.image_gen import ImageGenerator
gen = ImageGenerator(domain='育儿教育')
subdir = 'YYYY-MM-DD-主题'
gen.generate_compare_card(left_title='...', left_items=[...], right_title='...', right_items=[...], top_title='...', filename='compare.jpg', subdir=subdir)
gen.generate_info_card(title='...', subtitle='...', items=[{'label':'...','desc':'...'}], filename='info.jpg', subdir=subdir)
gen.generate_quote_card(quote='...', author='...', filename='quote.jpg', subdir=subdir)
gen.generate_cta_card(line1='...', line2='...', cta_text='👇 评论区聊聊', filename='cta.jpg', subdir=subdir)
"
```

domain 选择：育儿/教育→育儿教育，职场/技术→职场干货，情感/婚姻→情感故事，健康/运动→健康养生

### 3.4 保存

用 Write 工具将文章写入 `~/.claude/skills/article-viral/data/generated/YYYY-MM-DD-主题.md`

---

## Step 4: 发布

```bash
cd ~/.claude/skills/article-viral && python3 -m scripts.cli publish "data/generated/YYYY-MM-DD-主题.md"
```

---

## Step 5: 告知用户

> ✅ 文章已保存到公众号草稿箱！
>
> 📝 标题：{标题}
> 📊 字数：约{N}字
> 🖼️ 配图：{N}张
>
> 去公众号后台看看排版，没问题就可以发布了。

---

## 注意

- 所有命令由你自动执行，用户零操作（仅扫码登录需要用户动手）
- 发布固定为「保存草稿」，绝不自动发布
- cookie 过期时自动引导重新登录
