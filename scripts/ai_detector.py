"""AI 检测模块 - 本地统计算法初筛 + 第三方 API 精检"""
import os
import re
import math
from dataclasses import dataclass, field
from typing import Optional


# 中文 AI 高频连接词
AI_CONNECTORS = [
    "此外", "另外", "然而", "不过", "总之", "综上所述", "值得注意的是",
    "需要指出的是", "不可否认", "毋庸置疑", "总而言之", "由此可见",
    "换言之", "具体而言", "简而言之", "事实上", "实际上",
    "从某种程度上说", "与此同时", "更重要的是", "显而易见",
    "不言而喻", "归根结底", "一方面", "另一方面", "尤其是",
    "特别是", "首先", "其次", "最后", "总的来说",
    "在这个过程中", "从本质上讲", "客观来说", "不得不说",
]

# 口语化标记词
COLLOQUIAL_MARKERS = [
    "啊", "呢", "吧", "嘛", "哎", "哈", "嗯", "诶", "呀", "哦",
    "说实话", "讲真", "我觉得", "真的是", "太", "超", "巨",
    "绝了", "离谱", "搞笑", "牛逼", "卧槽", "好家伙", "不是",
    "你说", "咱", "整个人", "笑死", "哭了", "破防", "蚌埠住",
    "……", "!", "？", "...", "~",
]


@dataclass
class DetectionResult:
    local_score: float
    api_score: Optional[float] = None
    api_provider: Optional[str] = None
    risk_level: str = "low"
    suggestions: list = field(default_factory=list)
    flagged_sentences: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


class AIDetector:
    """AI 文本检测器：本地统计算法 + 可选 API 精检"""

    def __init__(self, api_key: str = None, threshold: int = 60):
        self.threshold = threshold
        self.api_key = api_key or self._load_api_key()

    def _load_api_key(self) -> Optional[str]:
        """从 .env 文件加载 API key"""
        env_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         ".baoyu-skills", ".env"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        ]
        for env_path in env_paths:
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GPTZERO_API_KEY="):
                            return line.split("=", 1)[1].strip().strip("\"'")
                        if line.startswith("ZEROGPT_RAPIDAPI_KEY="):
                            return line.split("=", 1)[1].strip().strip("\"'")
        return None

    def _split_sentences(self, text: str) -> list:
        """中文分句"""
        text = re.sub(r'\s+', '', text)
        parts = re.split(r'[。！？；\n]+', text)
        return [s.strip() for s in parts if len(s.strip()) >= 4]

    def _split_paragraphs(self, text: str) -> list:
        """分段"""
        paras = re.split(r'\n\s*\n|\n', text)
        return [p.strip() for p in paras if len(p.strip()) >= 10]

    def _sentence_length_variance(self, sentences: list) -> float:
        """句长方差分析 — AI 文本句长趋于均匀，方差小"""
        if len(sentences) < 5:
            return 0.0
        lengths = [len(s) for s in sentences]
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return 0.0
        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        cv = math.sqrt(variance) / mean  # 变异系数
        # cv 越小 → 越均匀 → 越像 AI；cv 正常人写作约 0.4-0.8
        if cv < 0.2:
            return 95.0
        elif cv < 0.3:
            return 75.0
        elif cv < 0.4:
            return 55.0
        elif cv < 0.55:
            return 35.0
        elif cv < 0.7:
            return 20.0
        return 5.0

    def _connector_density(self, text: str) -> float:
        """连接词密度 — AI 爱用书面连接词"""
        text_len = len(text)
        if text_len < 100:
            return 0.0
        count = sum(text.count(c) for c in AI_CONNECTORS)
        density = count / (text_len / 500)  # 每500字出现次数
        if density > 5:
            return 95.0
        elif density > 3.5:
            return 80.0
        elif density > 2.5:
            return 60.0
        elif density > 1.5:
            return 40.0
        elif density > 0.8:
            return 20.0
        return 5.0

    def _repetition_pattern(self, sentences: list) -> float:
        """句式重复度 — AI 倾向重复相似的句式结构"""
        if len(sentences) < 8:
            return 0.0
        # 取每句前3个字作为句式指纹
        openings = [s[:3] for s in sentences if len(s) >= 3]
        if not openings:
            return 0.0
        unique_ratio = len(set(openings)) / len(openings)
        # unique_ratio 越小说明重复越多
        if unique_ratio < 0.3:
            return 90.0
        elif unique_ratio < 0.45:
            return 70.0
        elif unique_ratio < 0.6:
            return 50.0
        elif unique_ratio < 0.75:
            return 30.0
        return 10.0

    def _opening_diversity(self, paragraphs: list) -> float:
        """段首词多样性 — AI 段落开头模式化"""
        if len(paragraphs) < 4:
            return 0.0
        # 取每段前5个字
        openings = [p[:5] for p in paragraphs if len(p) >= 5]
        if len(openings) < 4:
            return 0.0
        # 检查相邻段落开头相似度
        similar_count = 0
        for i in range(len(openings) - 1):
            # 前2字相同视为相似
            if openings[i][:2] == openings[i + 1][:2]:
                similar_count += 1
        similar_ratio = similar_count / (len(openings) - 1)
        if similar_ratio > 0.5:
            return 90.0
        elif similar_ratio > 0.35:
            return 70.0
        elif similar_ratio > 0.2:
            return 45.0
        elif similar_ratio > 0.1:
            return 25.0
        return 5.0

    def _colloquial_score(self, text: str) -> float:
        """口语化程度 — 自然写作含语气词和不完整句，AI 缺乏这些"""
        text_len = len(text)
        if text_len < 100:
            return 0.0
        count = sum(text.count(m) for m in COLLOQUIAL_MARKERS)
        density = count / (text_len / 200)  # 每200字口语标记数
        # density 越低越像 AI（返回 AI 嫌疑分数，所以反转）
        if density < 0.3:
            return 85.0
        elif density < 0.8:
            return 65.0
        elif density < 1.5:
            return 45.0
        elif density < 2.5:
            return 25.0
        return 5.0

    def _find_flagged_sentences(self, sentences: list) -> list:
        """找出高 AI 概率的句子"""
        flagged = []
        for s in sentences:
            reasons = []
            # 含 AI 连接词开头
            for c in AI_CONNECTORS:
                if s.startswith(c):
                    reasons.append(f"以AI连接词「{c}」开头")
                    break
            # 句长在平均范围（过于工整）
            if 20 <= len(s) <= 35:
                reasons.append("句长过于工整(20-35字)")
            if reasons:
                flagged.append({"sentence": s, "reasons": reasons})
        return flagged[:10]  # 最多返回10条

    def _generate_suggestions(self, details: dict) -> list:
        """根据各指标得分生成改写建议"""
        suggestions = []
        if details.get("sentence_variance", 0) > 50:
            suggestions.append(
                "句子长短变化不够：试着混合短句(<10字)和长句(>40字)，"
                "模拟说话时的呼吸节奏")
        if details.get("connector_density", 0) > 50:
            suggestions.append(
                "书面连接词太多：删掉「此外」「总之」「值得注意的是」等，"
                "改用口语过渡或直接换行")
        if details.get("repetition", 0) > 50:
            suggestions.append(
                "句式重复度高：避免连续用相同句式开头，"
                "穿插疑问句、感叹句、不完整句")
        if details.get("opening_diversity", 0) > 50:
            suggestions.append(
                "段落开头太模式化：用对话、数字、场景描写等开头，"
                "避免每段都是陈述句")
        if details.get("colloquial", 0) > 50:
            suggestions.append(
                "口语化不足：加入「说实话」「讲真」「我觉得」等主观表达，"
                "适当使用语气词和省略号")
        return suggestions

    def _local_detect(self, text: str) -> DetectionResult:
        """本地算法综合检测"""
        sentences = self._split_sentences(text)
        paragraphs = self._split_paragraphs(text)

        details = {
            "sentence_variance": self._sentence_length_variance(sentences),
            "connector_density": self._connector_density(text),
            "repetition": self._repetition_pattern(sentences),
            "opening_diversity": self._opening_diversity(paragraphs),
            "colloquial": self._colloquial_score(text),
        }

        # 加权计算：连接词和口语化权重最高
        weights = {
            "sentence_variance": 0.15,
            "connector_density": 0.25,
            "repetition": 0.15,
            "opening_diversity": 0.15,
            "colloquial": 0.30,
        }
        score = sum(details[k] * weights[k] for k in weights)
        score = round(min(100, max(0, score)), 1)

        # 确定风险等级
        if score <= 10:
            risk_level = "low"
        elif score <= 70:
            risk_level = "medium"
        else:
            risk_level = "high"

        flagged = self._find_flagged_sentences(sentences)
        suggestions = self._generate_suggestions(details)

        return DetectionResult(
            local_score=score,
            risk_level=risk_level,
            suggestions=suggestions,
            flagged_sentences=flagged,
            details=details,
        )

    def _call_gptzero(self, text: str) -> Optional[dict]:
        """调用 GPTZero API"""
        try:
            import httpx
        except ImportError:
            return None
        if not self.api_key:
            return None
        try:
            resp = httpx.post(
                "https://api.gptzero.me/v2/predict/text",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                },
                json={"document": text},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                doc = data.get("documents", [{}])[0]
                return {
                    "score": round(
                        doc.get("completely_generated_prob", 0) * 100, 1),
                    "provider": "gptzero",
                }
        except Exception:
            pass
        return None

    def _call_zerogpt(self, text: str) -> Optional[dict]:
        """调用 ZeroGPT API (RapidAPI)"""
        try:
            import httpx
        except ImportError:
            return None
        if not self.api_key:
            return None
        try:
            resp = httpx.post(
                "https://zerogpt.p.rapidapi.com/api/v1/detectText",
                headers={
                    "Content-Type": "application/json",
                    "x-rapidapi-key": self.api_key,
                    "x-rapidapi-host": "zerogpt.p.rapidapi.com",
                },
                json={"input_text": text},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "score": round(
                        data.get("is_gpt_generated", 0), 1),
                    "provider": "zerogpt",
                }
        except Exception:
            pass
        return None

    def detect(self, text: str, local_only: bool = False) -> DetectionResult:
        """完整检测流程：本地初筛，超阈值时调 API 精检"""
        # 清洗 Markdown 格式
        clean = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE)
        clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)
        clean = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', clean)
        clean = re.sub(r'[*_~`>]', '', clean)
        clean = clean.strip()

        if len(clean) < 50:
            return DetectionResult(local_score=0, risk_level="low",
                                   suggestions=["文本过短，无法有效检测"])

        result = self._local_detect(clean)

        if local_only or result.local_score <= self.threshold:
            return result

        # 超阈值，尝试 API 精检
        api_result = self._call_gptzero(clean)
        if not api_result:
            api_result = self._call_zerogpt(clean)

        if api_result:
            result.api_score = api_result["score"]
            result.api_provider = api_result["provider"]
            # 综合分数：本地 40% + API 60%
            combined = result.local_score * 0.4 + api_result["score"] * 0.6
            combined = round(combined, 1)
            if combined <= 10:
                result.risk_level = "low"
            elif combined <= 70:
                result.risk_level = "medium"
            else:
                result.risk_level = "high"

        return result
