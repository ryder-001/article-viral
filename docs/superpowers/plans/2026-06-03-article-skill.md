# 公众号爆款文章自动生成 Skill 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个 Claude Code Skill，从多平台采集爆款文章、提取写作规则、生成爆款文章并积累经验。

**Architecture:** 主 Skill (`/article`) + Python 工具集。Skill 作为入口调度 Claude 完成分析和生成，Python 脚本负责采集和数据存储。规则存储在 Markdown 文件中，原始数据存储在 SQLite 中。

**Tech Stack:** Python 3.10+, httpx, beautifulsoup4, lxml, sqlite3, pyyaml, click

---

## 文件结构

| 文件路径 | 职责 |
|---------|------|
| `skills/article.md` | Skill 入口，定义子命令和工作流 |
| `scripts/collect/__init__.py` | 采集模块包初始化，导出所有采集器 |
| `scripts/collect/base.py` | 采集器基类，定义接口和通用逻辑 |
| `scripts/collect/wechat.py` | 微信公众号采集器 |
| `scripts/collect/toutiao.py` | 今日头条采集器 |
| `scripts/collect/baijiahao.py` | 百家号采集器 |
| `scripts/collect/weibo.py` | 微博采集器 |
| `scripts/collect/sohu.py` | 搜狐采集器 |
| `scripts/collect/zhihu.py` | 知乎采集器 |
| `scripts/db.py` | SQLite 数据层 |
| `scripts/analyze.py` | 分析辅助（统计、格式化） |
| `scripts/cli.py` | CLI 入口 |
| `config.yaml` | 配置文件 |
| `requirements.txt` | Python 依赖 |
| `tests/test_db.py` | 数据层测试 |
| `tests/test_collect_base.py` | 采集器基类测试 |
| `tests/test_cli.py` | CLI 测试 |

---

### Task 1: 项目脚手架与依赖

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `scripts/__init__.py`
- Create: `scripts/collect/__init__.py`
- Create: `data/rules/.gitkeep`
- Create: `data/generated/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```
httpx>=0.27.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pyyaml>=6.0
click>=8.1.0
pytest>=8.0.0
```

- [ ] **Step 2: 创建 config.yaml**

```yaml
domain: "通用"
keywords:
  - "热门话题"

platforms:
  wechat: true
  toutiao: true
  baijiahao: true
  weibo: true
  sohu: true
  zhihu: true

collect:
  max_articles_per_platform: 20
  request_delay: [2, 5]
  user_agents: []
  proxy: ""

viral_threshold:
  wechat_likes: 1000
  toutiao_comments: 500
  weibo_reposts: 1000
  zhihu_upvotes: 1000
  default_reads: 100000

generate:
  min_words: 800
  max_words: 1500
  style: "通俗易懂，有故事性"
```

- [ ] **Step 3: 创建目录结构和空 __init__.py**

```bash
mkdir -p scripts/collect data/rules data/generated tests
touch scripts/__init__.py scripts/collect/__init__.py tests/__init__.py
touch data/rules/.gitkeep data/generated/.gitkeep
```

- [ ] **Step 4: 安装依赖验证**

Run: `pip install -r requirements.txt`
Expected: 所有包安装成功

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config.yaml scripts/ data/ tests/
git commit -m "feat: 初始化项目结构和依赖"
```

---

### Task 2: SQLite 数据层

**Files:**
- Create: `scripts/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: 编写 db.py 测试**

```python
# tests/test_db.py
import os
import tempfile
import pytest
from scripts.db import ArticleDB


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = ArticleDB(path)
    yield database
    database.close()
    os.unlink(path)


def test_insert_and_get_article(db):
    article = {
        "platform": "wechat",
        "url": "https://mp.weixin.qq.com/s/abc123",
        "title": "测试爆款标题",
        "content": "这是正文内容",
        "author": "测试作者",
        "domain": "科技",
        "publish_time": "2026-06-01",
        "read_count": 100000,
        "like_count": 5000,
        "comment_count": 200,
        "share_count": 1000,
        "is_viral": True,
    }
    article_id = db.insert_article(article)
    assert article_id > 0

    fetched = db.get_article(article_id)
    assert fetched["title"] == "测试爆款标题"
    assert fetched["platform"] == "wechat"


def test_get_unanalyzed_articles(db):
    for i in range(3):
        db.insert_article({
            "platform": "toutiao",
            "url": f"https://toutiao.com/{i}",
            "title": f"文章{i}",
            "content": f"内容{i}",
            "is_viral": True,
        })
    articles = db.get_unanalyzed_articles()
    assert len(articles) == 3


def test_mark_analyzed(db):
    aid = db.insert_article({
        "platform": "weibo",
        "url": "https://weibo.com/1",
        "title": "微博爆款",
        "content": "内容",
        "is_viral": True,
    })
    db.mark_analyzed(aid)
    articles = db.get_unanalyzed_articles()
    assert len(articles) == 0


def test_insert_generated(db):
    gen_id = db.insert_generated({
        "title": "生成的文章",
        "content": "生成内容",
        "domain": "科技",
        "topic": "AI趋势",
        "rules_version": "v1",
        "source_articles": "[1,2,3]",
    })
    assert gen_id > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/test_db.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 db.py**

```python
# scripts/db.py
import sqlite3
from datetime import datetime
from typing import Optional


class ArticleDB:
    def __init__(self, db_path: str = "data/articles.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                platform TEXT NOT NULL,
                url TEXT UNIQUE,
                title TEXT NOT NULL,
                content TEXT,
                author TEXT,
                domain TEXT,
                publish_time TEXT,
                collect_time TEXT,
                read_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                is_viral BOOLEAN DEFAULT 0,
                analyzed BOOLEAN DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS generated (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                domain TEXT,
                topic TEXT,
                rules_version TEXT,
                generate_time TEXT,
                source_articles TEXT
            );
        """)
        self.conn.commit()

    def insert_article(self, article: dict) -> int:
        article.setdefault("collect_time", datetime.now().isoformat())
        fields = [
            "platform", "url", "title", "content", "author",
            "domain", "publish_time", "collect_time",
            "read_count", "like_count", "comment_count",
            "share_count", "is_viral"
        ]
        values = [article.get(f) for f in fields]
        placeholders = ",".join(["?"] * len(fields))
        columns = ",".join(fields)
        cursor = self.conn.execute(
            f"INSERT OR IGNORE INTO articles ({columns}) VALUES ({placeholders})",
            values
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_article(self, article_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_unanalyzed_articles(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM articles WHERE analyzed = 0 AND is_viral = 1 ORDER BY collect_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_viral_articles(self, domain: str = None, limit: int = 10) -> list[dict]:
        if domain:
            rows = self.conn.execute(
                "SELECT * FROM articles WHERE is_viral = 1 AND domain = ? ORDER BY read_count DESC LIMIT ?",
                (domain, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM articles WHERE is_viral = 1 ORDER BY read_count DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_analyzed(self, article_id: int):
        self.conn.execute(
            "UPDATE articles SET analyzed = 1 WHERE id = ?", (article_id,)
        )
        self.conn.commit()

    def insert_generated(self, record: dict) -> int:
        record.setdefault("generate_time", datetime.now().isoformat())
        fields = ["title", "content", "domain", "topic", "rules_version", "generate_time", "source_articles"]
        values = [record.get(f) for f in fields]
        placeholders = ",".join(["?"] * len(fields))
        columns = ",".join(fields)
        cursor = self.conn.execute(
            f"INSERT INTO generated ({columns}) VALUES ({placeholders})",
            values
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        viral = self.conn.execute("SELECT COUNT(*) FROM articles WHERE is_viral = 1").fetchone()[0]
        analyzed = self.conn.execute("SELECT COUNT(*) FROM articles WHERE analyzed = 1").fetchone()[0]
        generated = self.conn.execute("SELECT COUNT(*) FROM generated").fetchone()[0]
        return {"total": total, "viral": viral, "analyzed": analyzed, "generated": generated}

    def close(self):
        self.conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/test_db.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/db.py tests/test_db.py
git commit -m "feat: 实现 SQLite 数据层"
```

---

### Task 3: 采集器基类

**Files:**
- Create: `scripts/collect/base.py`
- Create: `tests/test_collect_base.py`

- [ ] **Step 1: 编写基类测试**

```python
# tests/test_collect_base.py
import pytest
from scripts.collect.base import BaseCollector


class DummyCollector(BaseCollector):
    platform = "dummy"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        return [{"title": f"Article {keyword}", "url": "https://example.com/1"}]

    async def fetch_article(self, url: str) -> dict:
        return {"title": "Test", "content": "Content", "url": url}

    async def get_metrics(self, url: str) -> dict:
        return {"read_count": 200000, "like_count": 5000}


def test_is_viral_above_threshold():
    c = DummyCollector(viral_threshold=100000)
    assert c.is_viral({"read_count": 200000}) is True


def test_is_viral_below_threshold():
    c = DummyCollector(viral_threshold=100000)
    assert c.is_viral({"read_count": 5000}) is False


def test_platform_name():
    c = DummyCollector(viral_threshold=100000)
    assert c.platform == "dummy"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/test_collect_base.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现基类**

```python
# scripts/collect/base.py
import asyncio
import random
import httpx
from abc import ABC, abstractmethod

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


class BaseCollector(ABC):
    platform: str = ""

    def __init__(self, viral_threshold: int = 100000, delay: tuple = (2, 5),
                 user_agents: list = None, proxy: str = ""):
        self.viral_threshold = viral_threshold
        self.delay = delay
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.proxy = proxy or None

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    async def _request(self, url: str, **kwargs) -> httpx.Response:
        await asyncio.sleep(random.uniform(*self.delay))
        async with httpx.AsyncClient(proxy=self.proxy, timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers=self._get_headers(), **kwargs)
            response.raise_for_status()
            return response

    def is_viral(self, metrics: dict) -> bool:
        read_count = metrics.get("read_count", 0) or 0
        like_count = metrics.get("like_count", 0) or 0
        comment_count = metrics.get("comment_count", 0) or 0
        share_count = metrics.get("share_count", 0) or 0
        total_engagement = like_count + comment_count + share_count
        return read_count >= self.viral_threshold or total_engagement >= (self.viral_threshold // 10)

    @abstractmethod
    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        """搜索文章列表，返回 [{title, url, ...}]"""
        pass

    @abstractmethod
    async def fetch_article(self, url: str) -> dict:
        """抓取文章全文，返回 {title, content, author, publish_time, ...}"""
        pass

    @abstractmethod
    async def get_metrics(self, url: str) -> dict:
        """获取文章指标，返回 {read_count, like_count, comment_count, share_count}"""
        pass
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/test_collect_base.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/collect/base.py tests/test_collect_base.py
git commit -m "feat: 实现采集器基类 BaseCollector"
```

---

### Task 4: 平台采集器实现（微信公众号 + 今日头条）

**Files:**
- Create: `scripts/collect/wechat.py`
- Create: `scripts/collect/toutiao.py`

- [ ] **Step 1: 实现微信公众号采集器**

```python
# scripts/collect/wechat.py
"""微信公众号采集器 - 通过搜狗微信搜索获取文章"""
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from .base import BaseCollector


class WechatCollector(BaseCollector):
    platform = "wechat"
    SEARCH_URL = "https://weixin.sogou.com/weixin"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        page = 1
        while len(results) < max_results:
            params = {"type": "2", "query": keyword, "page": str(page)}
            try:
                resp = await self._request(self.SEARCH_URL, params=params)
            except Exception:
                break
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select("div.txt-box")
            if not items:
                break
            for item in items:
                a = item.select_one("h3 a")
                if not a:
                    continue
                results.append({
                    "title": a.get_text(strip=True),
                    "url": a.get("href", ""),
                    "platform": self.platform,
                })
                if len(results) >= max_results:
                    break
            page += 1
        return results

    async def fetch_article(self, url: str) -> dict:
        resp = await self._request(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.select_one("#activity-name")
        content_div = soup.select_one("#js_content")
        author = soup.select_one("#js_name")
        publish_time = soup.select_one("#publish_time")
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": content_div.get_text(separator="\n", strip=True) if content_div else "",
            "author": author.get_text(strip=True) if author else "",
            "publish_time": publish_time.get_text(strip=True) if publish_time else "",
            "url": url,
            "platform": self.platform,
        }

    async def get_metrics(self, url: str) -> dict:
        # 微信文章阅读量需要特殊接口，这里返回默认值
        # 实际使用中可通过搜狗搜索结果页面的热度指标估算
        return {"read_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}
```

- [ ] **Step 2: 实现今日头条采集器**

```python
# scripts/collect/toutiao.py
"""今日头条采集器 - 通过头条搜索获取文章"""
import json
from bs4 import BeautifulSoup
from .base import BaseCollector


class ToutiaoCollector(BaseCollector):
    platform = "toutiao"
    SEARCH_URL = "https://so.toutiao.com/search"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        params = {"keyword": keyword, "pd": "information", "source": "search_subtab_switch"}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.result-content"):
            a = item.select_one("a")
            if not a:
                continue
            results.append({
                "title": a.get_text(strip=True),
                "url": a.get("href", ""),
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        resp = await self._request(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.select_one("h1") or soup.select_one("title")
        article = soup.select_one("article") or soup.select_one(".article-content")
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": article.get_text(separator="\n", strip=True) if article else "",
            "author": "",
            "publish_time": "",
            "url": url,
            "platform": self.platform,
        }

    async def get_metrics(self, url: str) -> dict:
        return {"read_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}
```

- [ ] **Step 3: Commit**

```bash
git add scripts/collect/wechat.py scripts/collect/toutiao.py
git commit -m "feat: 实现微信公众号和今日头条采集器"
```

---

### Task 5: 平台采集器实现（百家号 + 微博 + 搜狐 + 知乎）

**Files:**
- Create: `scripts/collect/baijiahao.py`
- Create: `scripts/collect/weibo.py`
- Create: `scripts/collect/sohu.py`
- Create: `scripts/collect/zhihu.py`

- [ ] **Step 1: 实现百家号采集器**

```python
# scripts/collect/baijiahao.py
"""百家号采集器 - 通过百度搜索筛选百家号文章"""
from bs4 import BeautifulSoup
from .base import BaseCollector


class BaijiahaoCollector(BaseCollector):
    platform = "baijiahao"
    SEARCH_URL = "https://www.baidu.com/s"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        params = {"wd": f"site:baijiahao.baidu.com {keyword}", "rn": str(min(max_results, 50))}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.result"):
            a = item.select_one("h3 a")
            if not a:
                continue
            results.append({
                "title": a.get_text(strip=True),
                "url": a.get("href", ""),
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        resp = await self._request(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.select_one("div.article-title h2") or soup.select_one("h1")
        content = soup.select_one("div.article-content") or soup.select_one("article")
        author = soup.select_one("span.author-name")
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": content.get_text(separator="\n", strip=True) if content else "",
            "author": author.get_text(strip=True) if author else "",
            "publish_time": "",
            "url": url,
            "platform": self.platform,
        }

    async def get_metrics(self, url: str) -> dict:
        return {"read_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}
```

- [ ] **Step 2: 实现微博采集器**

```python
# scripts/collect/weibo.py
"""微博采集器 - 通过微博搜索获取热门微博"""
from bs4 import BeautifulSoup
from .base import BaseCollector


class WeiboCollector(BaseCollector):
    platform = "weibo"
    SEARCH_URL = "https://s.weibo.com/weibo"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        params = {"q": keyword, "xsort": "hot", "suball": "1"}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.select("div.card-wrap"):
            content = card.select_one("p.txt")
            link = card.select_one("a[action-type='feed_list_url']")
            if not content:
                continue
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                url = "https://weibo.com" + url
            results.append({
                "title": content.get_text(strip=True)[:50],
                "url": url,
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        resp = await self._request(url)
        soup = BeautifulSoup(resp.text, "lxml")
        content = soup.select_one("div.weibo-text") or soup.select_one("div.card-text")
        return {
            "title": content.get_text(strip=True)[:50] if content else "",
            "content": content.get_text(separator="\n", strip=True) if content else "",
            "author": "",
            "publish_time": "",
            "url": url,
            "platform": self.platform,
        }

    async def get_metrics(self, url: str) -> dict:
        return {"read_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}
```

- [ ] **Step 3: 实现搜狐采集器**

```python
# scripts/collect/sohu.py
"""搜狐采集器 - 通过搜狐搜索获取文章"""
from bs4 import BeautifulSoup
from .base import BaseCollector


class SohuCollector(BaseCollector):
    platform = "sohu"
    SEARCH_URL = "https://search.sohu.com/"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        params = {"keyword": keyword, "type": "news"}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.news-list li, div.result-item"):
            a = item.select_one("a")
            if not a:
                continue
            url = a.get("href", "")
            if url and not url.startswith("http"):
                url = "https:" + url
            results.append({
                "title": a.get_text(strip=True),
                "url": url,
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        resp = await self._request(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.select_one("h1") or soup.select_one("title")
        content = soup.select_one("article") or soup.select_one("div.article")
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": content.get_text(separator="\n", strip=True) if content else "",
            "author": "",
            "publish_time": "",
            "url": url,
            "platform": self.platform,
        }

    async def get_metrics(self, url: str) -> dict:
        return {"read_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}
```

- [ ] **Step 4: 实现知乎采集器**

```python
# scripts/collect/zhihu.py
"""知乎采集器 - 通过知乎搜索获取高赞回答和文章"""
from bs4 import BeautifulSoup
from .base import BaseCollector


class ZhihuCollector(BaseCollector):
    platform = "zhihu"
    SEARCH_URL = "https://www.zhihu.com/search"

    async def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        results = []
        params = {"type": "content", "q": keyword}
        try:
            resp = await self._request(self.SEARCH_URL, params=params)
        except Exception:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.ContentItem"):
            title_el = item.select_one("h2") or item.select_one("a.ContentItem-title")
            link = item.select_one("a[data-za-detail-view-path-module]")
            if not title_el:
                continue
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                url = "https://www.zhihu.com" + url
            results.append({
                "title": title_el.get_text(strip=True),
                "url": url,
                "platform": self.platform,
            })
            if len(results) >= max_results:
                break
        return results

    async def fetch_article(self, url: str) -> dict:
        resp = await self._request(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.select_one("h1.QuestionHeader-title") or soup.select_one("h1")
        content = soup.select_one("div.RichContent-inner") or soup.select_one("article")
        author = soup.select_one("span.AuthorInfo-name")
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": content.get_text(separator="\n", strip=True) if content else "",
            "author": author.get_text(strip=True) if author else "",
            "publish_time": "",
            "url": url,
            "platform": self.platform,
        }

    async def get_metrics(self, url: str) -> dict:
        return {"read_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}
```

- [ ] **Step 5: 更新 collect/__init__.py 导出所有采集器**

```python
# scripts/collect/__init__.py
from .wechat import WechatCollector
from .toutiao import ToutiaoCollector
from .baijiahao import BaijiahaoCollector
from .weibo import WeiboCollector
from .sohu import SohuCollector
from .zhihu import ZhihuCollector

ALL_COLLECTORS = {
    "wechat": WechatCollector,
    "toutiao": ToutiaoCollector,
    "baijiahao": BaijiahaoCollector,
    "weibo": WeiboCollector,
    "sohu": SohuCollector,
    "zhihu": ZhihuCollector,
}
```

- [ ] **Step 6: Commit**

```bash
git add scripts/collect/
git commit -m "feat: 实现全部平台采集器（百家号、微博、搜狐、知乎）"
```

---

### Task 6: CLI 入口

**Files:**
- Create: `scripts/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: 编写 CLI 测试**

```python
# tests/test_cli.py
import os
import tempfile
from click.testing import CliRunner
from scripts.cli import cli


def test_cli_stats():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "total" in result.output or "文章" in result.output


def test_cli_collect_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["collect", "--help"])
    assert result.exit_code == 0
    assert "keyword" in result.output or "关键词" in result.output
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 CLI**

```python
# scripts/cli.py
"""命令行入口 - 提供 collect/analyze/generate/stats 子命令"""
import asyncio
import json
import os
import yaml
import click
from scripts.db import ArticleDB
from scripts.collect import ALL_COLLECTORS


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_db(config: dict = None) -> ArticleDB:
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "articles.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return ArticleDB(db_path)


@click.group()
def cli():
    """公众号爆款文章工具"""
    pass


@cli.command()
@click.argument("keyword")
@click.option("--domain", default=None, help="文章领域")
@click.option("--platform", default=None, help="指定平台（逗号分隔），不指定则用配置")
@click.option("--max-results", default=20, help="每个平台最大采集数")
def collect(keyword, domain, platform, max_results):
    """采集爆款文章"""
    config = load_config()
    db = get_db(config)
    domain = domain or config.get("domain", "通用")
    threshold = config.get("viral_threshold", {}).get("default_reads", 100000)
    delay = tuple(config.get("collect", {}).get("request_delay", [2, 5]))
    proxy = config.get("collect", {}).get("proxy", "")

    if platform:
        platforms = [p.strip() for p in platform.split(",")]
    else:
        platforms = [k for k, v in config.get("platforms", {}).items() if v]

    async def run():
        total_collected = 0
        for pname in platforms:
            if pname not in ALL_COLLECTORS:
                click.echo(f"[跳过] 未知平台: {pname}")
                continue
            click.echo(f"[采集] {pname} - 关键词: {keyword}")
            collector = ALL_COLLECTORS[pname](
                viral_threshold=threshold, delay=delay, proxy=proxy
            )
            try:
                articles = await collector.search(keyword, max_results=max_results)
                click.echo(f"  找到 {len(articles)} 篇文章")
                for art in articles:
                    try:
                        full = await collector.fetch_article(art["url"])
                        full["domain"] = domain
                        full["is_viral"] = True  # 来自搜索结果默认标记
                        db.insert_article(full)
                        total_collected += 1
                    except Exception as e:
                        click.echo(f"  [错误] 抓取失败: {e}")
            except Exception as e:
                click.echo(f"  [错误] 搜索失败: {e}")
        click.echo(f"\n完成！共采集 {total_collected} 篇文章")

    asyncio.run(run())
    db.close()


@cli.command()
def stats():
    """显示数据统计"""
    db = get_db()
    s = db.get_stats()
    click.echo(f"文章总数: {s['total']}")
    click.echo(f"爆款文章: {s['viral']}")
    click.echo(f"已分析: {s['analyzed']}")
    click.echo(f"已生成: {s['generated']}")
    db.close()


@cli.command()
@click.option("--limit", default=50, help="分析文章数量上限")
@click.option("--output", default=None, help="规则输出文件路径")
def analyze(limit, output):
    """导出未分析的爆款文章供 Claude 分析"""
    db = get_db()
    articles = db.get_unanalyzed_articles(limit=limit)
    if not articles:
        click.echo("没有待分析的文章")
        db.close()
        return
    # 输出文章摘要供 Claude 分析
    output_data = []
    for art in articles:
        output_data.append({
            "id": art["id"],
            "title": art["title"],
            "content": art["content"][:2000] if art.get("content") else "",
            "platform": art["platform"],
            "read_count": art.get("read_count", 0),
            "like_count": art.get("like_count", 0),
        })
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        click.echo(f"已导出 {len(output_data)} 篇文章到 {output}")
    else:
        click.echo(json.dumps(output_data, ensure_ascii=False, indent=2))
    db.close()


@cli.command()
@click.argument("article_ids", nargs=-1, type=int)
def mark_analyzed(article_ids):
    """标记文章为已分析"""
    db = get_db()
    for aid in article_ids:
        db.mark_analyzed(aid)
    click.echo(f"已标记 {len(article_ids)} 篇文章为已分析")
    db.close()


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/test_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/cli.py tests/test_cli.py
git commit -m "feat: 实现 CLI 命令行入口"
```

---

### Task 7: Skill 文件

**Files:**
- Create: `skills/article.md`
- Create: `data/rules/global_rules.md`

- [ ] **Step 1: 创建初始爆文规则文件**

```markdown
# 爆文规则 - 通用

> 版本: v1 | 更新时间: 2026-06-03 | 来源文章数: 0

## 标题规则
- 控制在 15-25 字之间
- 使用数字增加具体感（如"3个方法"、"5分钟学会"）
- 制造信息差（"原来…"、"竟然…"）
- 对比式标题点击率高（A vs B、以前 vs 现在）
- 使用疑问句引发好奇（"为什么…？"）

## 结构规则
- 首段必须在 3 句话内制造悬念或引发共鸣
- 全文 800-1500 字为最佳阅读区间
- 使用小标题分割段落，每段不超过 150 字
- 关键信息加粗或用 emoji 标记重点
- 结尾设置互动引导（提问、投票、征集评论）

## 内容规则
- 开头用故事、数据或反常识观点切入
- 每 200-300 字插入一个案例、数据或金句
- 使用口语化表达，像朋友聊天
- 制造"获得感"——读者读完觉得学到了东西
- 适当制造争议性，引发评论和转发

## 互动规则
- 文末设置开放式问题引导评论
- 使用"你觉得呢？""你有类似经历吗？"等话术
- 在文中埋设讨论点，让读者有参与感
```

- [ ] **Step 2: 创建 Skill 文件**

```markdown
---
name: article
description: 公众号爆款文章自动采集、分析和生成。支持子命令：collect（采集）、analyze（分析）、generate（生成）、rules（查看规则）。
---

# 公众号爆款文章 Skill

根据用户的子命令执行对应流程。

## 子命令路由

解析用户输入的参数，确定执行哪个子命令：
- `collect [关键词]` → 执行采集流程
- `analyze` → 执行分析流程
- `generate [主题]` → 执行生成流程
- `rules` → 查看当前规则
- 无参数 → 执行全流程（采集 → 分析 → 生成）

## collect 流程

1. 运行采集脚本：
   ```bash
   cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m scripts.cli collect "<关键词>" --domain "<领域>"
   ```
2. 报告采集结果

## analyze 流程

1. 运行导出脚本获取待分析文章：
   ```bash
   cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m scripts.cli analyze --output data/temp_articles.json
   ```
2. 读取导出的文章数据
3. 逐篇分析文章的爆款特征：
   - 标题特征：字数、句式、情绪词、数字使用
   - 结构特征：段落数、段落长度、首段钩子
   - 内容特征：故事性、数据引用、情感共鸣点
   - 互动特征：引导评论手法、结尾 CTA
4. 与现有规则文件合并，更新 `data/rules/` 下对应领域的规则
5. 标记已分析的文章：
   ```bash
   cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m scripts.cli mark-analyzed <id1> <id2> ...
   ```

## generate 流程

1. 读取规则文件 `data/rules/global_rules.md`（或领域规则）
2. 运行命令获取参考爆款文章：
   ```bash
   cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m scripts.cli analyze --limit 5
   ```
3. 基于规则和参考文章，生成一篇爆款文章：
   - 严格遵循规则文件中的标题/结构/内容/互动规则
   - 参考爆款文章的风格但不抄袭
   - 生成完整的公众号文章（含标题、正文、结尾互动）
4. 将生成的文章保存到 `data/generated/` 目录
5. 展示生成结果供用户审阅

## rules 流程

1. 读取并展示 `data/rules/` 目录下所有规则文件
2. 运行统计：
   ```bash
   cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m scripts.cli stats
   ```
3. 展示规则摘要和数据统计

## 全流程（无参数）

依次执行：collect → analyze → generate，用户只需提供关键词和主题即可一键完成。
```

- [ ] **Step 3: 创建 skills 目录**

```bash
mkdir -p /Users/yjl/Documents/dev/code/51talk/article_tools/skills
```

- [ ] **Step 4: Commit**

```bash
git add skills/article.md data/rules/global_rules.md
git commit -m "feat: 创建 article skill 和初始爆文规则"
```

---

### Task 8: 集成测试与验收

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_integration.py
"""集成测试 - 验证完整流程可运行"""
import os
import tempfile
import pytest
from click.testing import CliRunner
from scripts.cli import cli
from scripts.db import ArticleDB


@pytest.fixture
def setup_env(tmp_path):
    """创建临时环境"""
    db_path = str(tmp_path / "test.db")
    os.environ["ARTICLE_DB_PATH"] = db_path
    db = ArticleDB(db_path)
    # 插入测试数据
    db.insert_article({
        "platform": "wechat",
        "url": "https://mp.weixin.qq.com/s/test1",
        "title": "震惊！3个方法让你的效率提升10倍",
        "content": "在这个信息爆炸的时代，如何提升效率成了每个人的必修课。今天分享3个经过验证的方法...",
        "author": "效率达人",
        "domain": "职场",
        "read_count": 150000,
        "like_count": 8000,
        "comment_count": 500,
        "is_viral": True,
    })
    db.insert_article({
        "platform": "zhihu",
        "url": "https://zhihu.com/answer/test2",
        "title": "为什么越努力越焦虑？心理学家揭示真相",
        "content": "这个问题困扰了无数年轻人。从心理学角度来看，焦虑的本质是...",
        "author": "心理博士",
        "domain": "心理",
        "read_count": 200000,
        "like_count": 12000,
        "comment_count": 1200,
        "is_viral": True,
    })
    yield db
    db.close()


def test_stats_with_data(setup_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0
    assert "2" in result.output  # 2篇文章


def test_analyze_exports_articles(setup_env, tmp_path):
    runner = CliRunner()
    output_file = str(tmp_path / "export.json")
    result = runner.invoke(cli, ["analyze", "--output", output_file])
    assert result.exit_code == 0
    assert os.path.exists(output_file)


def test_mark_analyzed(setup_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["mark-analyzed", "1", "2"])
    assert result.exit_code == 0
    articles = setup_env.get_unanalyzed_articles()
    assert len(articles) == 0
```

- [ ] **Step 2: 运行集成测试**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/test_integration.py -v`
Expected: 3 passed

- [ ] **Step 3: 运行全部测试确认无回归**

Run: `cd /Users/yjl/Documents/dev/code/51talk/article_tools && python -m pytest tests/ -v`
Expected: All passed

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: 添加集成测试"
```

---

## 完成标准

- [ ] 所有测试通过 (`python -m pytest tests/ -v`)
- [ ] `python -m scripts.cli stats` 正常输出
- [ ] `python -m scripts.cli collect "AI" --platform wechat` 可执行（可能因反爬失败，但不应崩溃）
- [ ] `skills/article.md` 存在且格式正确
- [ ] `data/rules/global_rules.md` 包含初始规则
