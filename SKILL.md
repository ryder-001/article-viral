---
name: wechat-publish
description: "一键生成公众号爆款文章并自动发布到微信公众号编辑器。输入主题即可完成全流程：AI写爆款文章 + 自动配图 + Playwright自动化粘贴到公众号后台编辑器 + 自动保存草稿。零配置开箱即用，个人未认证订阅号可用。触发词: '发公众号', '写公众号文章', '公众号发布', '发布文章', '写一篇文章发到公众号', '帮我发一篇', '写篇文章并发布', '/publish', '一键发布', '自动发布公众号', '生成并发布文章', '公众号一键发文', '帮我写篇公众号文章'"
---

# 公众号文章一键发布

说出主题 → AI写爆款文章 → 自动生成配图 → 自动粘贴到公众号编辑器 → 保存草稿。

**零配置，首次使用扫码登录一次即可。个人未认证订阅号可用。**

---

## Step 1: 环境初始化

每次执行前自动运行，已安装则秒过（7天缓存）：

```bash
SKILL_DIR="$(find "${SKILL_SEARCH_PATHS:-$HOME}" -type f -name "SKILL.md" -path "*/wechat-publish/*" -exec dirname {} \; 2>/dev/null | head -1)"
cd "$SKILL_DIR" && python3 scripts/setup.py
```

> setup.py 自动完成：pip 依赖安装 + Playwright Chromium 安装 + 数据目录创建 + 默认配置生成。

---

## Step 2: 检查微信登录态

```bash
cd "$SKILL_DIR" && python3 -m scripts.cli login
```

- 如果 wechat 显示 `✓ 已登录` → 继续 Step 3
- 如果 wechat 显示 `✗ 未登录` → 执行登录：

```bash
cd "$SKILL_DIR" && python3 -m scripts.cli login wechat
```

会弹出浏览器，用户扫码登录后 cookie 自动保存，后续不再需要。

---

## Step 3: 生成爆款文章 + 配图

根据用户给的**主题**，按以下流程生成内容：

### 3.1 读取规则

读取 `$SKILL_DIR/data/rules/global_rules.md`，获取标题/结构/内容/互动规则。

### 3.2 写文章（Markdown格式）

严格遵循规则，生成完整公众号文章：

| 要素 | 要求 |
|------|------|
| 标题 | H1，18-30字，数字+情绪触发+具体承诺 |
| 开篇 | 3句内抓住注意力（反常识/痛点/故事） |
| 正文 | 800-1500字，3-4个小标题，每段配案例 |
| 结尾 | 金句+开放式问题+转发引导 |
| 风格 | 口语化，像朋友聊天，多用"你""我" |
| 配图 | 文中用 `![描述](images/...)` 标记位置 |

### 3.3 生成配图

用 Python 调用 `scripts/image_gen.py` 生成 3-4 张配图：

```python
from scripts.image_gen import ImageGenerator
gen = ImageGenerator(domain='育儿教育')  # 按主题选domain
subdir = 'YYYY-MM-DD-主题关键词'

# 从以下类型中选择 3-4 张：
gen.generate_compare_card(...)   # 对比图（正反对比、前后对比）
gen.generate_info_card(...)      # 信息卡（方法步骤、要点归纳）
gen.generate_quote_card(...)     # 金句卡（核心观点）
gen.generate_cta_card(...)       # 互动尾图（引导评论转发）
```

### 3.4 保存文件

文章保存到：`$SKILL_DIR/data/generated/YYYY-MM-DD-主题.md`
图片保存到：`$SKILL_DIR/data/generated/images/YYYY-MM-DD-主题/`

---

## Step 4: 一键发布到公众号

```bash
cd "$SKILL_DIR" && python3 -m scripts.cli publish "data/generated/YYYY-MM-DD-主题.md"
```

自动完成：
1. Markdown → 公众号排版 HTML（内联CSS，自动选主题色）
2. 本地配图 → base64 嵌入（编辑器会自动上传到微信CDN）
3. Playwright 打开浏览器 → 加载 cookie → 进入编辑器
4. 自动填写标题 + 粘贴排版正文
5. 等待图片上传 → 自动点击「保存为草稿」

---

## Step 5: 告知用户结果

发布成功后告诉用户：

> 文章已保存到公众号草稿箱！
> - 标题：{标题}
> - 字数：{字数}
> - 配图：{N}张
>
> 请到公众号后台检查排版，确认无误后点击发布。

---

## 默认值

| 参数 | 默认值 |
|------|--------|
| 字数 | 800-1500 |
| 排版主题 | auto（按标题关键词自动选色） |
| 配图数量 | 3-4张 |
| 发布模式 | 保存草稿（不会直接发布） |

## 故障排查

| 问题 | 解决 |
|------|------|
| cookie 过期 | `python3 -m scripts.cli login wechat` 重新扫码 |
| 浏览器启动失败 | `python3 -m playwright install chromium` |
| 正文为空 | 确保 Markdown 有 H1 标题且图片路径正确 |
| 图片不显示 | 编辑器需要几秒上传 base64 图片，等待即可 |
