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
