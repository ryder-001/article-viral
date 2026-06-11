---
name: article-viral
description: "多平台内容工具：采集热点 → 写文 → 配图 → AI检测 → 发布到公众号。输入主题即可全自动完成。触发词: '发公众号', '写公众号文章', '公众号发布', '发布文章', '写一篇文章发到公众号', '帮我发一篇', '写篇文章并发布', '/publish', '一键发布', '自动发布公众号', '生成并发布文章', '公众号一键发文', '帮我写篇公众号文章', '爆文', '爆款文章', '/article', '采集文章', '生成文章', '流量文', '热点文章', '写文章'"
---

# 多平台内容工具 — 全自动流水线

用户只需说出主题（或让系统自动推荐热点），Claude 自动完成全部步骤。

**项目路径**: `~/Documents/dev/code/51talk/article_tools`

---

## Step 1: 环境初始化

自动执行，对用户透明：

```bash
cd ~/Documents/dev/code/51talk/article_tools && python3 scripts/setup.py
```

---

## Step 2: 确保微信已登录

```bash
cd ~/Documents/dev/code/51talk/article_tools && python3 -m scripts.cli login
```

- wechat 显示 `✓ 已登录` → 继续
- wechat 显示 `✗ 未登录` → 告诉用户"需要扫码登录微信公众号"，然后执行：

```bash
cd ~/Documents/dev/code/51talk/article_tools && python3 -m scripts.cli login wechat
```

---

## Step 3: 热点采集分析（可选）

如果用户没有指定主题，或要求"写个热点文章"：

```bash
cd ~/Documents/dev/code/51talk/article_tools && python3 -m scripts.cli hot --limit 10
```

从热榜中挑选 2-3 个适合公众号的选题推荐给用户，让用户选择或自己指定。

如果用户已给出明确主题，跳过此步。

---

## Step 4: 选题确定

- 用户指定主题 → 直接使用
- 用户从热榜选择 → 使用对应热点
- 可执行关键词采集获取参考素材：

```bash
cd ~/Documents/dev/code/51talk/article_tools && python3 -m scripts.cli collect "关键词" --platform toutiao --no-authors
```

---

## Step 5: 写文章

### 5.1 读取规则

读取 `~/Documents/dev/code/51talk/article_tools/data/rules/global_rules.md`

### 5.2 生成 Markdown 文章

根据用户主题 + 规则 + 参考素材，生成完整文章：

| 要素 | 要求 |
|------|------|
| 标题 | H1，18-30字，数字+情绪触发+具体承诺 |
| 开篇 | 3句内抓注意力（反常识/痛点/故事） |
| 正文 | 800-1500字，3-4个H2小标题，每段配案例 |
| 结尾 | 金句+开放式问题+转发引导 |
| 风格 | 口语化，像朋友聊天，多用"你""我" |
| 配图标记 | 用 `![描述](prompt: 生图提示词)` 标记需要配图的位置 |

### 5.3 Anti-AI 写作要求

写作时主动规避 AI 痕迹：
- 句长方差要大（长短句交替，避免均匀句式）
- 减少"然而""此外""总之"等连接词
- 段首用词多样化（不要每段都用"首先""其次"）
- 加入口语化表达、不完整句、感叹句
- 插入个人经历或"听朋友说"等主观叙述

### 5.4 保存文章

用 Write 工具将文章写入：
`~/Documents/dev/code/51talk/article_tools/data/generated/YYYY-MM-DD-主题.md`

---

## Step 6: AI 检测

```bash
cd ~/Documents/dev/code/51talk/article_tools && python3 -m scripts.cli detect "data/generated/YYYY-MM-DD-主题.md"
```

判断标准：
- 分数 ≤ 40 → ✅ 放行，继续下一步
- 分数 41-70 → ⚠️ 警告，告知用户但继续
- 分数 > 70 → ❌ 阻断，根据建议改写文章后重新检测

---

## Step 7: 配图

优先使用 `baoyu-image-gen` skill 生成 AI 配图：
- 根据文章中 `![描述](prompt: ...)` 标记生成对应图片
- 生成后替换文章中的图片路径

如果 baoyu-image-gen 不可用或失败，fallback 到 Pillow 卡片生成：

```python
from scripts.image_gen import ImageGenerator
gen = ImageGenerator(domain='通用')
# 生成对比卡片、信息卡片、金句卡片、CTA卡片
```

---

## Step 8: 封面图

根据文章在卡片中的位置选择封面比例：

### 头条位置（第1篇）
- 比例：2.35:1 横向宽图
- 底部 20% 留白（公众号会叠加标题）
- 视觉重心在上半部

### 非头条位置（第2-8篇）
- 比例：1:1 正方形
- 文字可居中

使用 `baoyu-cover-image` skill 生成封面图，指定对应 aspect ratio。

---

## Step 9: 发布

```bash
cd ~/Documents/dev/code/51talk/article_tools && python3 -m scripts.cli publish "data/generated/YYYY-MM-DD-主题.md"
```

固定为「保存草稿」模式，绝不自动发布。

---

## Step 10: 报告结果

> ✅ 文章已保存到公众号草稿箱！
>
> 📝 标题：{标题}
> 📊 字数：约{N}字
> 🖼️ 配图：{N}张
> 🔍 AI检测：{分数}/100（{风险等级}）
>
> 去公众号后台看看排版，没问题就可以发布了。

---

## 注意事项

- 所有命令由 Claude 自动执行，用户零操作（仅扫码登录需要用户动手）
- 发布固定为「保存草稿」，绝不自动群发
- cookie 过期时自动引导重新登录
- 领域为通用（时事、商业、社会、生活方式都可写）
- 配图优先 AI 生图（baoyu-image-gen），失败才用 Pillow
