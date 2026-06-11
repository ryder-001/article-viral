"""SQLite 数据层"""
import sqlite3
from datetime import datetime
from typing import Optional


class ArticleDB:
    def __init__(self, db_path: str = "data/articles.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                platform TEXT NOT NULL,
                url TEXT UNIQUE,
                title TEXT NOT NULL,
                content TEXT,
                author TEXT,
                author_id TEXT,
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
            CREATE TABLE IF NOT EXISTS authors (
                id INTEGER PRIMARY KEY,
                platform TEXT NOT NULL,
                name TEXT NOT NULL,
                author_url TEXT UNIQUE,
                avatar TEXT,
                description TEXT,
                follower_count INTEGER DEFAULT 0,
                article_count INTEGER DEFAULT 0,
                total_read_count INTEGER DEFAULT 0,
                level TEXT,
                verified BOOLEAN DEFAULT 0,
                verified_info TEXT,
                collect_time TEXT,
                update_time TEXT
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

    def _migrate(self):
        """兼容旧数据库：自动添加缺失的字段"""
        cursor = self.conn.execute("PRAGMA table_info(articles)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        migrations = [
            ("author_id", "TEXT"),
            ("domain", "TEXT"),
            ("publish_time", "TEXT"),
        ]
        for col, col_type in migrations:
            if col not in existing_cols:
                self.conn.execute(
                    f"ALTER TABLE articles ADD COLUMN {col} {col_type}"
                )
        self.conn.commit()

    def insert_article(self, article: dict) -> int:
        article.setdefault("collect_time", datetime.now().isoformat())
        fields = [
            "platform", "url", "title", "content", "author", "author_id",
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
            "SELECT * FROM articles WHERE analyzed = 0 AND is_viral = 1 "
            "ORDER BY collect_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_viral_articles(self, domain: str = None, limit: int = 10) -> list[dict]:
        if domain:
            rows = self.conn.execute(
                "SELECT * FROM articles WHERE is_viral = 1 AND domain = ? "
                "ORDER BY read_count DESC LIMIT ?",
                (domain, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM articles WHERE is_viral = 1 "
                "ORDER BY read_count DESC LIMIT ?",
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
        fields = [
            "title", "content", "domain", "topic",
            "rules_version", "generate_time", "source_articles"
        ]
        values = [record.get(f) for f in fields]
        placeholders = ",".join(["?"] * len(fields))
        columns = ",".join(fields)
        cursor = self.conn.execute(
            f"INSERT INTO generated ({columns}) VALUES ({placeholders})",
            values
        )
        self.conn.commit()
        return cursor.lastrowid

    def upsert_author(self, author: dict) -> int:
        """插入或更新作者信息"""
        author.setdefault("collect_time", datetime.now().isoformat())
        author["update_time"] = datetime.now().isoformat()
        # 检查是否已存在
        existing = self.conn.execute(
            "SELECT id FROM authors WHERE author_url = ?",
            (author.get("author_url"),)
        ).fetchone()
        if existing:
            fields_to_update = [
                "name", "avatar", "description", "follower_count",
                "article_count", "total_read_count", "level",
                "verified", "verified_info", "update_time"
            ]
            sets = ", ".join([f"{f} = ?" for f in fields_to_update])
            values = [author.get(f) for f in fields_to_update]
            values.append(existing[0])
            self.conn.execute(
                f"UPDATE authors SET {sets} WHERE id = ?", values
            )
            self.conn.commit()
            return existing[0]
        else:
            fields = [
                "platform", "name", "author_url", "avatar", "description",
                "follower_count", "article_count", "total_read_count",
                "level", "verified", "verified_info", "collect_time", "update_time"
            ]
            values = [author.get(f) for f in fields]
            placeholders = ",".join(["?"] * len(fields))
            columns = ",".join(fields)
            cursor = self.conn.execute(
                f"INSERT INTO authors ({columns}) VALUES ({placeholders})",
                values
            )
            self.conn.commit()
            return cursor.lastrowid

    def get_author_by_url(self, author_url: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM authors WHERE author_url = ?", (author_url,)
        ).fetchone()
        return dict(row) if row else None

    def get_top_authors(self, platform: str = None, limit: int = 10) -> list[dict]:
        if platform:
            rows = self.conn.execute(
                "SELECT * FROM authors WHERE platform = ? "
                "ORDER BY follower_count DESC LIMIT ?",
                (platform, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM authors ORDER BY follower_count DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_article_metrics(self, article_id: int, metrics: dict):
        """更新文章的阅读指标"""
        sets = []
        values = []
        for key in ["read_count", "like_count", "comment_count", "share_count"]:
            if key in metrics and metrics[key]:
                sets.append(f"{key} = ?")
                values.append(metrics[key])
        if sets:
            values.append(article_id)
            self.conn.execute(
                f"UPDATE articles SET {', '.join(sets)} WHERE id = ?", values
            )
            self.conn.commit()

    def get_stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        viral = self.conn.execute(
            "SELECT COUNT(*) FROM articles WHERE is_viral = 1"
        ).fetchone()[0]
        analyzed = self.conn.execute(
            "SELECT COUNT(*) FROM articles WHERE analyzed = 1"
        ).fetchone()[0]
        generated = self.conn.execute(
            "SELECT COUNT(*) FROM generated"
        ).fetchone()[0]
        authors = self.conn.execute(
            "SELECT COUNT(*) FROM authors"
        ).fetchone()[0]
        with_metrics = self.conn.execute(
            "SELECT COUNT(*) FROM articles WHERE read_count > 0 OR like_count > 0"
        ).fetchone()[0]
        return {
            "total": total, "viral": viral,
            "analyzed": analyzed, "generated": generated,
            "authors": authors, "with_metrics": with_metrics
        }

    def close(self):
        self.conn.close()
