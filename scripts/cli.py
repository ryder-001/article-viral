"""命令行入口 - 提供 collect/analyze/generate/stats/rules 子命令"""
import asyncio
import json
import os
from datetime import datetime
import yaml
import click
from scripts.db import ArticleDB
from scripts.collect import ALL_COLLECTORS
from scripts.browser_fetcher import BrowserMetricsFetcher
from scripts.login_manager import (
    interactive_login, has_valid_cookies,
    list_saved_logins, ensure_login
)
from scripts.rules import (
    load_all_rules, load_rule, get_rules_summary, get_combined_rules
)


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config.yaml"
        )
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_db() -> ArticleDB:
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "articles.db"
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return ArticleDB(db_path)


@click.group()
def cli():
    """公众号爆款文章工具"""
    pass


@cli.command()
@click.argument("keyword")
@click.option("--domain", default=None, help="文章领域")
@click.option("--platform", default=None, help="指定平台（逗号分隔）")
@click.option("--max-results", default=20, help="每个平台最大采集数")
@click.option("--fetch-metrics/--no-metrics", default=True,
              help="是否获取阅读指标")
@click.option("--fetch-authors/--no-authors", default=True,
              help="是否获取作者信息")
def collect(keyword, domain, platform, max_results, fetch_metrics,
            fetch_authors):
    """采集爆款文章"""
    config = load_config()
    db = get_db()
    domain = domain or config.get("domain", "通用")
    threshold = config.get("viral_threshold", {}).get(
        "default_reads", 100000)
    delay = tuple(config.get("collect", {}).get("request_delay", [2, 5]))
    proxy = config.get("collect", {}).get("proxy", "")

    if platform:
        platforms = [p.strip() for p in platform.split(",")]
    else:
        platforms = [k for k, v in config.get("platforms", {}).items() if v]

    async def run():
        total_collected = 0
        authors_collected = 0
        metrics_collected = 0
        # 启动浏览器用于获取指标
        fetcher = None
        if fetch_metrics:
            fetcher = BrowserMetricsFetcher(headless=True)
            await fetcher.start()
            click.echo("[浏览器] 已启动，用于采集阅读指标")
        try:
            for pname in platforms:
                if pname not in ALL_COLLECTORS:
                    click.echo(f"[跳过] 未知平台: {pname}")
                    continue
                click.echo(f"[采集] {pname} - 关键词: {keyword}")
                collector = ALL_COLLECTORS[pname](
                    viral_threshold=threshold, delay=delay, proxy=proxy
                )
                try:
                    articles = await collector.search(
                        keyword, max_results=max_results)
                    click.echo(f"  找到 {len(articles)} 篇文章")
                    for art in articles:
                        try:
                            full = await collector.fetch_article(
                                art["url"])
                            if not full or not full.get("title"):
                                full = {
                                    "title": art.get("title", ""),
                                    "content": art.get("content", ""),
                                    "author": art.get("author", ""),
                                    "author_url": art.get(
                                        "author_url", ""),
                                    "publish_time": "",
                                    "url": art["url"],
                                    "platform": art["platform"],
                                    "read_count": art.get(
                                        "read_count", 0),
                                    "like_count": art.get(
                                        "like_count", 0),
                                    "comment_count": art.get(
                                        "comment_count", 0),
                                    "share_count": art.get(
                                        "share_count", 0),
                                }
                            # 合并搜索结果中的指标
                            for key in ["read_count", "like_count",
                                        "comment_count", "share_count"]:
                                sv = art.get(key, 0) or 0
                                fv = full.get(key, 0) or 0
                                full[key] = max(sv, fv)
                            # 浏览器获取真实指标
                            if fetcher and full.get("url"):
                                try:
                                    metrics = await fetcher.get_metrics(
                                        full["url"], pname)
                                    for key in ["read_count",
                                                "like_count",
                                                "comment_count",
                                                "share_count"]:
                                        mv = metrics.get(key, 0) or 0
                                        fv = full.get(key, 0) or 0
                                        full[key] = max(mv, fv)
                                    # 合并浏览器获取到的作者和时间
                                    if metrics.get("author") and not full.get("author"):
                                        full["author"] = metrics["author"]
                                    if metrics.get("publish_time") and not full.get("publish_time"):
                                        full["publish_time"] = metrics["publish_time"]
                                    if any(metrics.get(k, 0)
                                           for k in ["read_count",
                                                     "like_count",
                                                     "comment_count"]):
                                        metrics_collected += 1
                                except Exception:
                                    pass
                            full["domain"] = domain
                            full["is_viral"] = True
                            if full.get("title"):
                                db.insert_article(full)
                                total_collected += 1
                            # 获取作者信息
                            author_url = (full.get("author_url")
                                          or art.get("author_url", ""))
                            if fetch_authors and author_url:
                                existing = db.get_author_by_url(
                                    author_url)
                                if not existing:
                                    author_info = (
                                        await
                                        collector.fetch_author_info(
                                            author_url))
                                    if (author_info
                                            and author_info.get("name")):
                                        author_info["platform"] = pname
                                        db.upsert_author(author_info)
                                        authors_collected += 1
                        except Exception as e:
                            fallback = {
                                "title": art.get("title", ""),
                                "content": art.get("content", ""),
                                "author": art.get("author", ""),
                                "url": art["url"],
                                "platform": art["platform"],
                                "domain": domain,
                                "is_viral": True,
                                "read_count": art.get("read_count", 0),
                                "like_count": art.get("like_count", 0),
                                "comment_count": art.get(
                                    "comment_count", 0),
                                "share_count": art.get("share_count", 0),
                            }
                            if fallback.get("title"):
                                db.insert_article(fallback)
                                total_collected += 1
                            else:
                                click.echo(f"  [错误] 抓取失败: {e}")
                except Exception as e:
                    click.echo(f"  [错误] 搜索失败: {e}")
        finally:
            if fetcher:
                await fetcher.close()
        click.echo(f"\n完成！共采集 {total_collected} 篇文章"
                   f"，{authors_collected} 位作者"
                   f"，{metrics_collected} 篇获取到指标数据")

    asyncio.run(run())
    db.close()


@cli.command()
def stats():
    """显示数据统计"""
    db = get_db()
    s = db.get_stats()
    click.echo(f"文章总数: {s['total']}")
    click.echo(f"爆款文章: {s['viral']}")
    click.echo(f"有指标数据: {s['with_metrics']}")
    click.echo(f"已分析: {s['analyzed']}")
    click.echo(f"已生成: {s['generated']}")
    click.echo(f"作者数: {s['authors']}")
    db.close()


@cli.command()
@click.option("--limit", default=50, help="分析文章数量上限")
@click.option("--output", default=None, help="输出文件路径")
@click.option("--with-rules/--no-rules", default=True,
              help="是否附带规则上下文")
def analyze(limit, output, with_rules):
    """导出未分析的爆款文章供分析（附带规则上下文）"""
    db = get_db()
    articles = db.get_unanalyzed_articles(limit=limit)
    if not articles:
        click.echo("没有待分析的文章")
        db.close()
        return
    output_data = {
        "articles": [],
        "meta": {
            "total": len(articles),
            "export_time": datetime.now().isoformat(),
        }
    }
    # 附带规则上下文
    if with_rules:
        rules = load_all_rules()
        output_data["rules"] = rules
        output_data["meta"]["rules_files"] = list(rules.keys())
        click.echo(f"已加载 {len(rules)} 个规则文件: "
                   f"{', '.join(rules.keys())}")
    for art in articles:
        output_data["articles"].append({
            "id": art["id"],
            "title": art["title"],
            "content": art["content"][:2000] if art.get("content") else "",
            "author": art.get("author", ""),
            "platform": art["platform"],
            "read_count": art.get("read_count", 0),
            "like_count": art.get("like_count", 0),
            "comment_count": art.get("comment_count", 0),
            "share_count": art.get("share_count", 0),
        })
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        click.echo(f"已导出 {len(output_data['articles'])} 篇文章到 {output}")
    else:
        click.echo(json.dumps(output_data, ensure_ascii=False, indent=2))
    db.close()


@cli.command("mark-analyzed")
@click.argument("article_ids", nargs=-1, type=int)
def mark_analyzed(article_ids):
    """标记文章为已分析"""
    db = get_db()
    for aid in article_ids:
        db.mark_analyzed(aid)
    click.echo(f"已标记 {len(article_ids)} 篇文章为已分析")
    db.close()


@cli.command()
@click.option("--platform", default=None, help="指定平台")
@click.option("--limit", default=10, help="数量限制")
@click.option("--output", default=None, help="输出文件路径")
def authors(platform, limit, output):
    """查看采集到的作者信息"""
    db = get_db()
    author_list = db.get_top_authors(platform=platform, limit=limit)
    if not author_list:
        click.echo("暂无作者数据")
        db.close()
        return
    output_data = []
    for a in author_list:
        output_data.append({
            "name": a["name"],
            "platform": a["platform"],
            "follower_count": a.get("follower_count", 0),
            "article_count": a.get("article_count", 0),
            "description": a.get("description", ""),
            "verified": a.get("verified", False),
            "verified_info": a.get("verified_info", ""),
            "author_url": a.get("author_url", ""),
        })
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        click.echo(f"已导出 {len(output_data)} 位作者到 {output}")
    else:
        click.echo(json.dumps(output_data, ensure_ascii=False, indent=2))
    db.close()


@cli.command()
@click.argument("platform", required=False)
def login(platform):
    """登录平台（弹出浏览器扫码/输密码），保存 cookie 供后续采集使用

    支持平台: toutiao, zhihu, weibo, wechat, baijiahao
    不指定平台则显示当前登录状态
    """
    if not platform:
        saved = list_saved_logins()
        all_platforms = ["toutiao", "zhihu", "weibo", "wechat", "baijiahao"]
        click.echo("=== 登录状态 ===")
        for p in all_platforms:
            status = "✓ 已登录" if p in saved else "✗ 未登录"
            click.echo(f"  {p}: {status}")
        click.echo("\n用法: python3 -m scripts.cli login <平台名>")
        return
    asyncio.run(interactive_login(platform))


@cli.command()
@click.option("--name", default=None, help="查看指定规则文件")
def rules(name):
    """查看当前积累的爆文规则"""
    if name:
        content = load_rule(name)
        if content:
            click.echo(content)
        else:
            click.echo(f"规则文件不存在: {name}.md")
    else:
        click.echo("=== 爆文规则库 ===\n")
        click.echo(get_rules_summary())
        click.echo("\n使用 --name <规则名> 查看具体内容")


@cli.command()
@click.argument("topic")
@click.option("--domain", default=None, help="文章领域")
@click.option("--ref-count", default=5, help="参考文章数量")
@click.option("--output", default=None, help="输出文件路径")
def generate(topic, domain, ref_count, output):
    """基于规则生成爆款文章的上下文包（供AI使用）"""
    config = load_config()
    db = get_db()
    domain = domain or config.get("domain", "通用")

    # 收集参考文章
    ref_articles = db.get_viral_articles(domain=domain, limit=ref_count)
    if not ref_articles:
        ref_articles = db.get_viral_articles(limit=ref_count)

    # 加载所有规则
    all_rules = load_all_rules()

    # 组装生成上下文包
    context = {
        "task": "generate_viral_article",
        "topic": topic,
        "domain": domain,
        "rules": all_rules,
        "reference_articles": [
            {
                "title": art["title"],
                "content": art["content"][:1500] if art.get("content")
                else "",
                "platform": art["platform"],
                "read_count": art.get("read_count", 0),
                "like_count": art.get("like_count", 0),
                "comment_count": art.get("comment_count", 0),
            }
            for art in ref_articles
        ],
        "generation_requirements": {
            "word_count": "800-1500字",
            "structure": "标题 + 正文 + 结尾互动",
            "style": "口语化，像朋友聊天",
            "rules_priority": [
                "global_rules（通用写作规则）",
                "content_strategy_rules（爆款策略）",
                "visual_rules（配图建议）",
            ],
        },
        "meta": {
            "rules_count": len(all_rules),
            "ref_articles_count": len(ref_articles),
            "generate_time": datetime.now().isoformat(),
        }
    }

    # 输出
    if not output:
        output = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "generated",
            f"{datetime.now().strftime('%Y-%m-%d')}-{topic}.json"
        )
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(context, f, ensure_ascii=False, indent=2)

    click.echo(f"=== 生成上下文包 ===")
    click.echo(f"主题: {topic}")
    click.echo(f"领域: {domain}")
    click.echo(f"规则文件: {', '.join(all_rules.keys())}")
    click.echo(f"参考文章: {len(ref_articles)} 篇")
    click.echo(f"输出到: {output}")
    click.echo(f"\n可将此文件喂给 AI 进行文章生成。")
    db.close()


if __name__ == "__main__":
    cli()

