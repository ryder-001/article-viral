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
from scripts.ai_detector import AIDetector


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


@cli.command()
@click.argument("markdown_file", type=click.Path(exists=True))
@click.option("--suggest/--no-suggest", default=True,
              help="是否给出改写建议")
@click.option("--local-only", is_flag=True, default=False,
              help="仅本地检测（不调用API）")
@click.option("--threshold", default=60, help="触发API精检的分数阈值")
def detect(markdown_file, suggest, local_only, threshold):
    """检测文章的 AI 生成概率

    \b
    示例:
      python3 -m scripts.cli detect article.md
      python3 -m scripts.cli detect article.md --local-only
      python3 -m scripts.cli detect article.md --threshold 50
    """
    with open(markdown_file, "r", encoding="utf-8") as f:
        text = f.read()

    detector = AIDetector(threshold=threshold)
    result = detector.detect(text, local_only=local_only)

    # 输出结果
    risk_icons = {"low": "✅", "medium": "⚠️", "high": "❌"}
    icon = risk_icons.get(result.risk_level, "?")

    click.echo(f"\n{'='*50}")
    click.echo(f"  AI 检测报告 - {os.path.basename(markdown_file)}")
    click.echo(f"{'='*50}")
    click.echo(f"\n  {icon} 风险等级: {result.risk_level.upper()}")
    click.echo(f"  本地算法分数: {result.local_score}/100")
    if result.api_score is not None:
        click.echo(f"  API 检测分数: {result.api_score}/100"
                   f" ({result.api_provider})")
    click.echo(f"\n  --- 各维度分数 ---")
    labels = {
        "sentence_variance": "句长方差",
        "connector_density": "连接词密度",
        "repetition": "句式重复度",
        "opening_diversity": "段首多样性",
        "colloquial": "口语化程度",
    }
    for key, label in labels.items():
        score = result.details.get(key, 0)
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        click.echo(f"  {label}: {bar} {score:.0f}")

    if suggest and result.suggestions:
        click.echo(f"\n  --- 改写建议 ---")
        for i, s in enumerate(result.suggestions, 1):
            click.echo(f"  {i}. {s}")

    if result.flagged_sentences:
        click.echo(f"\n  --- 高 AI 概率句子（前5条） ---")
        for item in result.flagged_sentences[:5]:
            click.echo(f"  • {item['sentence'][:40]}...")
            click.echo(f"    原因: {', '.join(item['reasons'])}")

    click.echo(f"\n{'='*50}\n")


@cli.command()
@click.argument("markdown_file", type=click.Path(exists=True))
@click.option("--title", default=None, help="文章标题（默认从md第一行H1提取）")
@click.option("--author", default="", help="作者名")
@click.option("--cover", default=None, type=click.Path(),
              help="封面图路径（默认用文章第一张图）")
@click.option("--theme", default="auto",
              help="排版主题: orange/blue/green/purple/cyan/pink/red/auto")
@click.option("--digest", default="", help="文章摘要（默认为空）")
@click.option("--publish-now/--draft-only", default=False,
              help="直接发布 or 仅保存草稿（默认仅草稿）")
@click.option("--html-only", is_flag=True, default=False,
              help="仅转换为HTML文件（不发布）")
@click.option("--api", "use_api", is_flag=True, default=False,
              help="使用微信API模式（需认证服务号 + .env 配置）")
@click.option("--output", default=None, help="HTML输出路径（配合--html-only）")
@click.option("--force", is_flag=True, default=False,
              help="跳过AI检测，强制发布")
@click.option("--skip-detect", is_flag=True, default=False,
              help="跳过AI检测环节")
def publish(markdown_file, title, author, cover, theme, digest,
            publish_now, html_only, use_api, output, force, skip_detect):
    """将 Markdown 文章发布到微信公众号

    默认使用 Playwright 自动化打开编辑器粘贴内容（适合个人号）。

    \b
    示例:
      # 默认：Playwright 自动化粘贴到编辑器
      python3 -m scripts.cli publish article.md
      # 仅生成HTML文件
      python3 -m scripts.cli publish article.md --html-only
      # API模式（需认证服务号）
      python3 -m scripts.cli publish article.md --api
    """
    from scripts.publish import extract_title, find_first_image
    from scripts.md_to_wechat import markdown_to_html, select_theme_by_content

    # 1. 读取 Markdown 文件
    with open(markdown_file, "r", encoding="utf-8") as f:
        md_content = f.read()
    click.echo(f"[读取] {markdown_file}")

    # 1.5 AI 检测环节
    if not skip_detect and not force:
        detector = AIDetector(threshold=60)
        ai_result = detector.detect(md_content, local_only=True)
        click.echo(f"[AI检测] 分数: {ai_result.local_score}/100"
                   f" ({ai_result.risk_level.upper()})")
        if ai_result.risk_level == "high":
            click.echo("[AI检测] ❌ AI 痕迹过重（>70），建议修改后重试")
            if ai_result.suggestions:
                for s in ai_result.suggestions:
                    click.echo(f"  → {s}")
            click.echo("[提示] 使用 --force 可跳过检测强制发布")
            return
        elif ai_result.risk_level == "medium":
            click.echo("[AI检测] ⚠️ 存在 AI 痕迹，建议优化：")
            if ai_result.suggestions:
                for s in ai_result.suggestions:
                    click.echo(f"  → {s}")
            click.echo("[继续] 风险可接受，继续发布流程...")

    # 2. 提取标题
    if not title:
        title = extract_title(md_content)
    if not title:
        click.echo("[错误] 无法提取标题，请用 --title 指定")
        return
    click.echo(f"[标题] {title}")

    # 3. 选择主题并转换 HTML
    if theme == "auto":
        theme = select_theme_by_content(title)
    click.echo(f"[主题] {theme}")
    html_content = markdown_to_html(md_content, theme)
    click.echo(f"[转换] Markdown → HTML 完成")

    # --- HTML-only 模式：输出文件后结束 ---
    if html_only:
        if not output:
            base = os.path.splitext(markdown_file)[0]
            output = base + ".html"
        with open(output, "w", encoding="utf-8") as f:
            f.write(html_content)
        click.echo(f"[输出] {output}")
        click.echo(f"\n排版HTML已生成，复制内容粘贴到公众号编辑器即可发布。")
        return

    # --- Playwright 自动化模式（默认） ---
    if not use_api:
        from scripts.wechat_publisher import publish_to_wechat_editor
        click.echo("[模式] Playwright 自动化")
        asyncio.run(publish_to_wechat_editor(markdown_file, title, html_content))
        return

    # --- API 模式（需认证服务号） ---
    click.echo("[模式] 微信 API")
    from scripts.publish import (
        load_wechat_credentials, get_access_token,
        upload_image, create_draft, publish_draft,
        process_content_images,
    )

    # 加载凭证并获取 token
    try:
        app_id, app_secret = load_wechat_credentials()
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        click.echo(f"[错误] {e}")
        click.echo("[提示] 个人未认证公众号请去掉 --api 使用默认模式")
        return
    try:
        access_token = get_access_token(app_id, app_secret)
    except RuntimeError as e:
        click.echo(f"[错误] {e}")
        return
    click.echo("[认证] access_token 获取成功")

    # 处理正文图片
    try:
        html_content = process_content_images(
            html_content, markdown_file, access_token)
        click.echo("[图片] 正文图片处理完成")
    except Exception as e:
        click.echo(f"[警告] 正文图片处理失败: {e}，继续执行...")

    # 6. 处理封面图
    cover_path = cover
    if not cover_path:
        cover_path = find_first_image(md_content, markdown_file)
    if not cover_path:
        click.echo("[错误] 未找到封面图，请用 --cover 指定")
        return
    try:
        thumb_media_id = upload_image(access_token, cover_path)
        click.echo(f"[封面] 上传成功: {os.path.basename(cover_path)}")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        click.echo(f"[错误] 封面上传失败: {e}")
        return

    # 7. 创建草稿
    try:
        media_id = create_draft(
            access_token, title, html_content,
            thumb_media_id, author=author, digest=digest
        )
        click.echo(f"[草稿] 创建成功！media_id: {media_id}")
    except RuntimeError as e:
        click.echo(f"[错误] 创建草稿失败: {e}")
        return

    # 8. 可选：直接发布
    if publish_now:
        try:
            publish_id = publish_draft(access_token, media_id)
            click.echo(f"[发布] 提交成功！publish_id: {publish_id}")
        except RuntimeError as e:
            click.echo(f"[错误] 发布失败: {e}")
            return
    else:
        click.echo("\n文章已保存到草稿箱，请前往公众号后台查看和发布。")


if __name__ == "__main__":
    cli()

