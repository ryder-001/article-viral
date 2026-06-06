"""自动配图生成模块 - 根据文章内容生成配套图片"""
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from typing import Optional

# 默认输出目录
DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "generated", "images"
)

# 字体查找
FONT_CANDIDATES = [
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/System/Library/Fonts/Supplemental/Songti.ttc',
    '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
]

# 配色方案
PALETTES = {
    'warm': {
        'bg': '#FFF8F0', 'text': '#3E2723', 'accent': '#FF7043',
        'muted': '#A1887F', 'light': '#FFFDF7',
    },
    'cool': {
        'bg': '#F5F7FA', 'text': '#1A237E', 'accent': '#42A5F5',
        'muted': '#78909C', 'light': '#ECEFF1',
    },
    'nature': {
        'bg': '#F1F8E9', 'text': '#33691E', 'accent': '#66BB6A',
        'muted': '#81C784', 'light': '#E8F5E9',
    },
}

# 领域→配色映射
DOMAIN_PALETTE = {
    '育儿教育': 'warm',
    '职场干货': 'cool',
    '情感故事': 'warm',
    '健康养生': 'nature',
}


def _find_font() -> str:
    """查找可用的中文字体路径"""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _get_fonts(font_path: str) -> dict:
    """加载不同尺寸的字体"""
    if not font_path:
        default = ImageFont.load_default()
        return {s: default for s in ['big', 'title', 'sub', 'small', 'quote']}
    return {
        'big': ImageFont.truetype(font_path, 48, index=0),
        'title': ImageFont.truetype(font_path, 36, index=0),
        'sub': ImageFont.truetype(font_path, 24, index=0),
        'small': ImageFont.truetype(font_path, 18, index=0),
        'quote': ImageFont.truetype(font_path, 80, index=0),
    }


class ImageGenerator:
    """文章配图生成器"""

    def __init__(self, output_dir: str = None, domain: str = '育儿教育'):
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.font_path = _find_font()
        self.fonts = _get_fonts(self.font_path)
        palette_name = DOMAIN_PALETTE.get(domain, 'warm')
        self.palette = PALETTES[palette_name]

    def _ensure_dir(self, subdir: str = None) -> str:
        """确保输出目录存在"""
        path = self.output_dir
        if subdir:
            path = os.path.join(path, subdir)
        os.makedirs(path, exist_ok=True)
        return path

    def generate_compare_card(
        self, left_title: str, left_items: list,
        right_title: str, right_items: list,
        top_title: str = '理想 VS 现实',
        filename: str = 'compare.jpg',
        subdir: str = None,
    ) -> str:
        """生成左右对比图"""
        out_dir = self._ensure_dir(subdir)
        img = Image.new('RGB', (900, 600), '#FFFFFF')
        draw = ImageDraw.Draw(img)

        # 左半（蓝色调）
        draw.rectangle([0, 0, 449, 600], fill='#E8F4FD')
        # 右半（橙色调）
        draw.rectangle([451, 0, 900, 600], fill='#FFF3E0')
        draw.rectangle([448, 0, 452, 600], fill='#CCCCCC')

        # 标题
        draw.text((450, 30), top_title, fill='#333333',
                  font=self.fonts['title'], anchor='mt')
        # 左侧
        draw.text((225, 100), left_title, fill='#1565C0',
                  font=self.fonts['sub'], anchor='mt')
        for i, line in enumerate(left_items[:8]):
            draw.text((225, 155 + i * 55), line, fill='#1565C0',
                      font=self.fonts['small'], anchor='mt')
        # 右侧
        draw.text((675, 100), right_title, fill='#E65100',
                  font=self.fonts['sub'], anchor='mt')
        for i, line in enumerate(right_items[:8]):
            draw.text((675, 155 + i * 55), line, fill='#E65100',
                      font=self.fonts['small'], anchor='mt')

        filepath = os.path.join(out_dir, filename)
        img.save(filepath, quality=90)
        return filepath

    def generate_info_card(
        self, title: str, subtitle: str,
        items: list, colors: list = None,
        filename: str = 'info_card.jpg',
        subdir: str = None,
    ) -> str:
        """生成信息图卡片（圆形图标+标签+描述）"""
        out_dir = self._ensure_dir(subdir)
        if not colors:
            colors = ['#FF7043', '#42A5F5', '#66BB6A', '#AB47BC']

        img = Image.new('RGB', (900, 600), self.palette['bg'])
        draw = ImageDraw.Draw(img)

        draw.text((450, 50), title, fill=self.palette['text'],
                  font=self.fonts['title'], anchor='mt')
        draw.text((450, 95), subtitle, fill=self.palette['muted'],
                  font=self.fonts['small'], anchor='mt')

        n = min(len(items), 4)
        spacing = 900 // (n + 1)
        for i in range(n):
            cx = spacing * (i + 1)
            cy = 330
            color = colors[i % len(colors)]
            item = items[i]
            label = item.get('label', '')
            desc = item.get('desc', '')

            draw.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], fill=color)
            draw.text((cx, cy - 15), str(i + 1), fill='#FFFFFF',
                      font=self.fonts['title'], anchor='mt')
            draw.text((cx, cy + 30), label, fill='#FFFFFF',
                      font=self.fonts['sub'], anchor='mt')
            draw.text((cx, cy + 120), desc, fill='#555555',
                      font=self.fonts['small'], anchor='mt')

        filepath = os.path.join(out_dir, filename)
        img.save(filepath, quality=90)
        return filepath

    def generate_data_compare(
        self, left_label: str, left_value: int, left_desc: str,
        right_label: str, right_value: int, right_desc: str,
        bottom_text: str = '',
        filename: str = 'data_compare.jpg',
        subdir: str = None,
    ) -> str:
        """生成数据对比图（带进度条，macOS设备框美化）"""
        out_dir = self._ensure_dir(subdir)
        img = Image.new('RGB', (900, 500), '#FFFFFF')
        draw = ImageDraw.Draw(img)

        # macOS 窗口边框
        draw.rectangle([40, 30, 860, 70], fill='#F0F0F0')
        draw.ellipse([55, 42, 67, 54], fill='#FF5F57')
        draw.ellipse([75, 42, 87, 54], fill='#FEBC2E')
        draw.ellipse([95, 42, 107, 54], fill='#28C840')
        draw.rectangle([40, 70, 860, 470], fill='#FAFAFA', outline='#E0E0E0')

        draw.text((450, 100), '数据对比', fill='#333333',
                  font=self.fonts['sub'], anchor='mt')

        # 左侧（红色/差）
        draw.text((250, 160), left_label, fill='#E53935',
                  font=self.fonts['sub'], anchor='mt')
        bar_width = int(260 * left_value / 100)
        draw.rectangle([120, 240, 380, 280], fill='#FFCDD2', outline='#E53935')
        draw.rectangle([120, 240, 120 + bar_width, 280], fill='#E53935')
        draw.text((250, 310), f'{left_value}%', fill='#E53935',
                  font=self.fonts['title'], anchor='mt')
        draw.text((250, 360), left_desc, fill='#999999',
                  font=self.fonts['small'], anchor='mt')

        # 右侧（绿色/好）
        draw.text((650, 160), right_label, fill='#43A047',
                  font=self.fonts['sub'], anchor='mt')
        bar_width = int(260 * right_value / 100)
        draw.rectangle([520, 240, 780, 280], fill='#C8E6C9', outline='#43A047')
        draw.rectangle([520, 240, 520 + bar_width, 280], fill='#43A047')
        draw.text((650, 310), f'{right_value}%', fill='#43A047',
                  font=self.fonts['title'], anchor='mt')
        draw.text((650, 360), right_desc, fill='#999999',
                  font=self.fonts['small'], anchor='mt')

        draw.text((450, 260), 'VS', fill='#AAAAAA',
                  font=self.fonts['title'], anchor='mm')
        if bottom_text:
            draw.text((450, 430), bottom_text, fill='#888888',
                      font=self.fonts['small'], anchor='mt')

        filepath = os.path.join(out_dir, filename)
        img.save(filepath, quality=90)
        return filepath

    def generate_quote_card(
        self, quote: str, author: str = '',
        filename: str = 'quote_card.jpg',
        subdir: str = None,
    ) -> str:
        """生成金句卡片（杂志风大留白）"""
        out_dir = self._ensure_dir(subdir)
        img = Image.new('RGB', (900, 600), self.palette['light'])
        draw = ImageDraw.Draw(img)

        # 大引号装饰
        draw.text((80, 100), '\u201c', fill='#E8D5B7',
                  font=self.fonts['quote'])

        # 金句（支持两行）
        lines = quote.split('\n') if '\n' in quote else [quote]
        y_start = 280 - (len(lines) - 1) * 35
        for i, line in enumerate(lines):
            draw.text((450, y_start + i * 70), line,
                      fill=self.palette['text'],
                      font=self.fonts['big'], anchor='mt')

        # 署名
        if author:
            draw.text((450, 450), author, fill=self.palette['muted'],
                      font=self.fonts['small'], anchor='mt')

        # 装饰线
        draw.rectangle([350, 520, 550, 522], fill='#E8D5B7')

        filepath = os.path.join(out_dir, filename)
        img.save(filepath, quality=90)
        return filepath

    def generate_cta_card(
        self, line1: str, line2: str,
        cta_text: str = '评论区聊聊',
        bottom_text: str = '',
        filename: str = 'cta_ending.jpg',
        subdir: str = None,
    ) -> str:
        """生成互动引导尾图（暖色渐变）"""
        out_dir = self._ensure_dir(subdir)
        img = Image.new('RGB', (900, 400), '#FFF3E0')
        # 渐变背景
        for y in range(400):
            r = min(255, max(0, int(255 - y * 0.02)))
            g = min(255, max(0, int(243 - y * 0.05)))
            b = min(255, max(0, int(224 - y * 0.1)))
            ImageDraw.Draw(img).line([(0, y), (900, y)], fill=(r, g, b))

        draw = ImageDraw.Draw(img)
        draw.text((450, 100), line1, fill='#4E342E',
                  font=self.fonts['title'], anchor='mt')
        draw.text((450, 150), line2, fill='#4E342E',
                  font=self.fonts['title'], anchor='mt')
        draw.text((450, 240), cta_text, fill='#6D4C41',
                  font=self.fonts['sub'], anchor='mt')
        if bottom_text:
            draw.text((450, 330), bottom_text, fill='#8D6E63',
                      font=self.fonts['small'], anchor='mt')

        filepath = os.path.join(out_dir, filename)
        img.save(filepath, quality=90)
        return filepath

    def generate_article_images(
        self, topic: str, domain: str = '育儿教育',
        subdir: str = None,
    ) -> dict:
        """为一篇文章生成全套配图，返回文件路径字典"""
        if not subdir:
            subdir = datetime.now().strftime('%Y-%m-%d')
        # 这里可以扩展更智能的逻辑，根据文章内容自动决定配图类型
        # 目前返回生成器实例和输出目录供外部调用
        return {
            'output_dir': self._ensure_dir(subdir),
            'generator': self,
            'subdir': subdir,
        }
