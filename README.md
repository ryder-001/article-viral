# 公众号文章一键发布

对 Claude 说"帮我写一篇关于XX的公众号文章"，自动完成全流程：

**写爆款文章 → 配图 → 粘贴到公众号编辑器 → 保存草稿**

个人未认证订阅号可用，零配置。

---

## 安装

一行命令：

```bash
git clone https://github.com/yourname/wechat-publish.git ~/.claude/skills/wechat-publish
```

装好了。剩下的事 Claude 全部自动搞定（装依赖、装浏览器、登录）。

---

## 使用

在 Claude Code 里直接说：

- "帮我写一篇关于高考的公众号文章"
- "写篇暑假孩子自律的文章发到公众号"
- "发一篇公众号文章，主题是职场焦虑"

第一次用会弹出浏览器让你扫码登录微信公众号后台，之后就不用了。

---

## 要求

- Python 3.9+（macOS/Linux/Windows 自带或自行安装）
- 一个微信公众号（个人号就行）
