"""Markdown → 微信公众号 HTML 转换器（内联CSS排版）

从 wechat-article-publisher 的 doocs 风格精简移植，
支持多种主题配色，所有样式内联（公众号要求）。
"""
import re

# 主题配色
THEMES = {
    "default": {
        "primary": "#3f51b5",
        "text": "#333333",
        "code_bg": "#f5f5f5",
        "quote_bg": "#f8f8f8",
        "quote_border": "#3f51b5",
    },
    "orange": {
        "primary": "#ff6d00",
        "text": "#333333",
        "code_bg": "#fff8f0",
        "quote_bg": "#fff8f0",
        "quote_border": "#ff6d00",
    },
    "green": {
        "primary": "#43a047",
        "text": "#333333",
        "code_bg": "#f1f8e9",
        "quote_bg": "#f1f8e9",
        "quote_border": "#43a047",
    },
    "purple": {
        "primary": "#7b1fa2",
        "text": "#333333",
        "code_bg": "#f3e5f5",
        "quote_bg": "#f3e5f5",
        "quote_border": "#7b1fa2",
    },
    "cyan": {
        "primary": "#00838f",
        "text": "#333333",
        "code_bg": "#e0f7fa",
        "quote_bg": "#e0f7fa",
        "quote_border": "#00838f",
    },
    "blue": {
        "primary": "#1565c0",
        "text": "#333333",
        "code_bg": "#e3f2fd",
        "quote_bg": "#e3f2fd",
        "quote_border": "#1565c0",
    },
    "pink": {
        "primary": "#d81b60",
        "text": "#333333",
        "code_bg": "#fce4ec",
        "quote_bg": "#fce4ec",
        "quote_border": "#d81b60",
    },
    "red": {
        "primary": "#c62828",
        "text": "#333333",
        "code_bg": "#ffebee",
        "quote_bg": "#ffebee",
        "quote_border": "#c62828",
    },
}


def process_inline(text: str, theme: dict) -> str:
    """处理行内元素：加粗、斜体、行内代码、链接"""
    # 加粗
    text = re.sub(
        r'\*\*(.+?)\*\*',
        lambda m: f'<strong style="color:{theme["primary"]};'
                  f'font-weight:bold;">{m.group(1)}</strong>',
        text
    )
    # 斜体
    text = re.sub(
        r'\*(.+?)\*',
        lambda m: f'<em>{m.group(1)}</em>',
        text
    )
    # 行内代码
    text = re.sub(
        r'`(.+?)`',
        lambda m: f'<code style="background:{theme["code_bg"]};'
                  f'padding:2px 6px;border-radius:3px;'
                  f'font-size:14px;color:{theme["primary"]};">'
                  f'{m.group(1)}</code>',
        text
    )
    # 链接 - 公众号不支持外链，显示为加粗文本
    text = re.sub(
        r'\[(.+?)\]\(.+?\)',
        lambda m: f'<strong style="color:{theme["primary"]};">'
                  f'{m.group(1)}</strong>',
        text
    )
    return text


def markdown_to_html(md_content: str, theme_name: str = "orange") -> str:
    """将 Markdown 转换为微信公众号 HTML（内联CSS）

    Args:
        md_content: Markdown 文本
        theme_name: 主题名称，可选值见 THEMES

    Returns:
        带内联样式的 HTML 字符串
    """
    theme = THEMES.get(theme_name, THEMES["orange"])
    lines = md_content.split('\n')
    html_parts = []
    in_code_block = False
    code_lines = []
    in_quote = False
    quote_lines = []
    in_list = False
    list_items = []
    list_type = "ul"
    list_counter = 0
    title_skipped = False

    def flush_quote():
        nonlocal in_quote, quote_lines
        if quote_lines:
            content = '<br/>'.join(quote_lines)
            html_parts.append(
                f'<blockquote style="border-left:4px solid '
                f'{theme["quote_border"]};background:{theme["quote_bg"]};'
                f'padding:12px 16px;margin:16px 0;'
                f'color:#666;font-size:15px;">{content}</blockquote>'
            )
            quote_lines = []
        in_quote = False

    def flush_list():
        nonlocal in_list, list_items, list_counter
        if list_items:
            for i, item in enumerate(list_items):
                if list_type == "ol":
                    prefix = f'<span style="color:{theme["primary"]};' \
                             f'font-weight:bold;">{i+1}. </span>'
                else:
                    prefix = f'<span style="color:{theme["primary"]};' \
                             f'font-weight:bold;">• </span>'
                html_parts.append(
                    f'<p style="font-size:16px;color:{theme["text"]};'
                    f'line-height:1.8;margin:6px 0;'
                    f'padding-left:8px;">{prefix}{item}</p>'
                )
            list_items = []
        in_list = False
        list_counter = 0

    for line in lines:
        # 跳过第一个 H1 标题（会单独填写到编辑器标题栏）
        if not title_skipped and line.strip().startswith('# ') and not line.strip().startswith('## '):
            title_skipped = True
            continue

        # 代码块
        if line.strip().startswith('```'):
            if in_code_block:
                code = '\n'.join(code_lines)
                html_parts.append(
                    f'<pre style="background:{theme["code_bg"]};'
                    f'padding:16px;border-radius:6px;overflow-x:auto;'
                    f'margin:16px 0;font-size:13px;line-height:1.6;">'
                    f'<code>{code}</code></pre>'
                )
                code_lines = []
                in_code_block = False
            else:
                if in_quote:
                    flush_quote()
                if in_list:
                    flush_list()
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line.replace('<', '&lt;').replace('>', '&gt;'))
            continue

        stripped = line.strip()

        # 空行
        if not stripped:
            if in_quote:
                flush_quote()
            if in_list:
                flush_list()
            continue

        # 引用块
        if stripped.startswith('>'):
            if in_list:
                flush_list()
            in_quote = True
            content = stripped.lstrip('>').strip()
            quote_lines.append(process_inline(content, theme))
            continue
        elif in_quote:
            flush_quote()

        # 标题
        h_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if h_match:
            if in_list:
                flush_list()
            level = len(h_match.group(1))
            text = h_match.group(2)
            sizes = {1: "22px", 2: "20px", 3: "18px", 4: "16px"}
            margins = {1: "24px 0 16px", 2: "22px 0 14px",
                       3: "20px 0 12px", 4: "18px 0 10px"}
            html_parts.append(
                f'<h{level} style="font-size:{sizes[level]};'
                f'color:{theme["primary"]};font-weight:bold;'
                f'margin:{margins[level]};text-align:left;">'
                f'{process_inline(text, theme)}</h{level}>'
            )
            continue

        # 图片
        img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', stripped)
        if img_match:
            if in_list:
                flush_list()
            alt = img_match.group(1)
            src = img_match.group(2)
            html_parts.append(
                f'<p style="text-align:center;margin:16px 0;">'
                f'<img src="{src}" alt="{alt}" '
                f'style="max-width:100%;border-radius:6px;" /></p>'
            )
            continue

        # 分隔线
        if re.match(r'^[-*_]{3,}$', stripped):
            if in_list:
                flush_list()
            html_parts.append(
                f'<hr style="border:none;border-top:1px solid #eee;'
                f'margin:24px 0;" />'
            )
            continue

        # 有序列表
        ol_match = re.match(r'^(\d+)[.)]\s+(.+)$', stripped)
        if ol_match:
            if not in_list or list_type != "ol":
                if in_list:
                    flush_list()
                in_list = True
                list_type = "ol"
            list_items.append(process_inline(ol_match.group(2), theme))
            continue

        # 无序列表
        ul_match = re.match(r'^[-*+]\s+(.+)$', stripped)
        if ul_match:
            if not in_list or list_type != "ul":
                if in_list:
                    flush_list()
                in_list = True
                list_type = "ul"
            list_items.append(process_inline(ul_match.group(1), theme))
            continue

        # 普通段落
        if in_list:
            flush_list()
        html_parts.append(
            f'<p style="font-size:16px;color:{theme["text"]};'
            f'line-height:2;margin:12px 0;text-align:justify;">'
            f'{process_inline(stripped, theme)}</p>'
        )

    # 清理残留状态
    if in_quote:
        flush_quote()
    if in_list:
        flush_list()
    if in_code_block and code_lines:
        code = '\n'.join(code_lines)
        html_parts.append(
            f'<pre style="background:{theme["code_bg"]};'
            f'padding:16px;border-radius:6px;overflow-x:auto;'
            f'margin:16px 0;font-size:13px;line-height:1.6;">'
            f'<code>{code}</code></pre>'
        )

    body = '\n'.join(html_parts)
    return (
        f'<section style="font-family:-apple-system,BlinkMacSystemFont,'
        f'\'Segoe UI\',Roboto,sans-serif;padding:16px;'
        f'max-width:100%;box-sizing:border-box;">{body}</section>'
    )


def select_theme_by_content(title: str) -> str:
    """根据标题内容智能选择主题"""
    keywords_map = {
        "orange": ["励志", "女性", "搞钱", "副业", "暑假", "孩子", "育儿",
                   "妈妈", "宝宝", "家长"],
        "blue": ["科技", "AI", "职场", "程序", "技术", "效率"],
        "green": ["健康", "养生", "环保", "自然", "饮食", "运动"],
        "pink": ["爱情", "情感", "恋爱", "婚姻", "浪漫"],
        "purple": ["品牌", "高端", "奢侈", "设计"],
        "cyan": ["旅行", "文艺", "摄影", "生活"],
        "red": ["节日", "活动", "新年", "春节", "圣诞"],
    }
    for theme_name, keywords in keywords_map.items():
        if any(kw in title for kw in keywords):
            return theme_name
    return "orange"
