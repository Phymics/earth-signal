import asyncio
import html
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


AUDIO_PATH = "audio/today-podcast.mp3"
VOICE = "zh-CN-XiaoxiaoNeural"
MAX_ITEMS_PER_SOURCE = 5

RSS_SOURCES = [
    {
        "name": "NYTimes Technology RSS",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "category": "科技",
        "trust": 7,
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "科技",
        "trust": 7,
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "科技",
        "trust": 8,
    },
    {
        "name": "NASA News",
        "url": "https://www.nasa.gov/news-release/feed/",
        "category": "科学",
        "trust": 8,
    },
]

FALLBACK_CANDIDATE = {
    "title": "NASA Expands Satellite Tools for Climate and Disaster Monitoring",
    "summary": "NASA is expanding satellite-based tools that help communities understand climate risks, track severe weather, and prepare for environmental change.",
    "sourceName": "Fallback Earth Signal Mock",
    "sourceUrl": "https://www.nasa.gov/",
    "published": "",
    "category": "科学",
}

TECH_KEYWORDS = {
    "ai": 8,
    "artificial intelligence": 8,
    "space": 7,
    "nasa": 7,
    "satellite": 7,
    "climate": 7,
    "energy": 6,
    "robot": 6,
    "robots": 6,
    "technology": 5,
    "chip": 5,
    "chips": 5,
    "data": 4,
    "security": 4,
}

PUBLIC_VALUE_KEYWORDS = {
    "global": 5,
    "cities": 5,
    "city": 4,
    "public": 5,
    "health": 6,
    "education": 6,
    "environment": 6,
    "climate": 6,
    "community": 5,
    "communities": 5,
    "energy": 4,
    "water": 4,
    "disaster": 5,
}

PROMO_KEYWORDS = {
    "sponsored": 8,
    "deal": 5,
    "sale": 5,
    "discount": 5,
    "buy": 4,
    "launches new app": 3,
    "raises": 3,
    "funding": 3,
}

TERM_MAP = {
    "ai": "人工智能",
    "artificial intelligence": "人工智能",
    "nasa": "NASA",
    "spacex": "SpaceX",
    "satellite": "卫星",
    "satellites": "卫星",
    "space": "太空",
    "climate": "气候",
    "energy": "能源",
    "robot": "机器人",
    "robots": "机器人",
    "chip": "芯片",
    "chips": "芯片",
    "security": "安全",
    "data": "数据",
    "health": "健康",
    "education": "教育",
    "city": "城市",
    "cities": "城市",
    "global": "全球",
    "environment": "环境",
    "technology": "科技",
    "governance": "治理",
}


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def get_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def child_text(node, names):
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return clean_text(found.text)
    for child in list(node):
        local = child.tag.split("}")[-1]
        if local in names and child.text:
            return clean_text(child.text)
    return ""


def child_attr(node, local_name, attr):
    for child in list(node):
        local = child.tag.split("}")[-1]
        if local == local_name and child.attrib.get(attr):
            return clean_text(child.attrib[attr])
    return ""


def fetch_source(source: dict) -> list:
    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "EarthSignalDemo/1.0"},
    )
    with urllib.request.urlopen(request, timeout=18, context=get_ssl_context()) as response:
        xml_text = response.read()
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")
    if not items:
        items = [node for node in root.iter() if node.tag.split("}")[-1] == "entry"]

    candidates = []
    for item in items[:MAX_ITEMS_PER_SOURCE]:
        title = child_text(item, ["title"])
        summary = child_text(item, ["description", "summary", "content", "encoded"])
        source_url = child_text(item, ["link"]) or child_attr(item, "link", "href") or source["url"]
        published = child_text(item, ["pubDate", "published", "updated"])
        if not title:
            continue
        candidates.append(
            {
                "title": title,
                "summary": summary or "This story comes from a trusted technology or science news feed.",
                "sourceName": source["name"],
                "sourceUrl": source_url,
                "published": published,
                "category": source["category"],
                "trust": source["trust"],
            }
        )
    return candidates


def fetch_rss_item() -> dict:
    candidates = fetch_all_candidates()
    selected, selection = select_best_story(candidates)
    selected["selection"] = selection
    return selected


def fetch_all_candidates() -> list:
    candidates = []
    for source in RSS_SOURCES:
        try:
            source_candidates = fetch_source(source)
            candidates.extend(source_candidates)
            print(f"Fetched {len(source_candidates)} items from {source['name']}")
        except Exception as exc:
            print(f"RSS source failed: {source['name']}: {exc}")
    if not candidates:
        print("All RSS sources failed, using fallback mock news.")
        return [FALLBACK_CANDIDATE.copy()]
    return candidates


def score_candidate(candidate: dict) -> tuple:
    text = f"{candidate['title']} {candidate['summary']}".lower()
    score = 0
    reasons = []

    source_score = candidate.get("trust", 5)
    score += source_score
    reasons.append(f"来源可信度 +{source_score}")

    tech_hits = []
    for keyword, points in TECH_KEYWORDS.items():
        if keyword in text:
            score += points
            tech_hits.append(keyword)
    if tech_hits:
        reasons.append("科技相关：" + ", ".join(tech_hits[:4]))

    public_hits = []
    for keyword, points in PUBLIC_VALUE_KEYWORDS.items():
        if keyword in text:
            score += points
            public_hits.append(keyword)
    if public_hits:
        reasons.append("公共价值：" + ", ".join(public_hits[:4]))

    summary_length = len(candidate.get("summary", ""))
    if summary_length < 50:
        score -= 6
        reasons.append("摘要过短 -6")
    elif summary_length > 120:
        score += 3
        reasons.append("信息量较完整 +3")

    promo_hits = []
    for keyword, points in PROMO_KEYWORDS.items():
        if keyword in text:
            score -= points
            promo_hits.append(keyword)
    if promo_hits:
        reasons.append("商业宣传倾向：" + ", ".join(promo_hits[:3]))

    if "review" in text or "hands-on" in text:
        score -= 4
        reasons.append("偏消费评测 -4")

    if any(word in text for word in ["climate", "health", "education", "satellite", "energy", "space"]):
        score += 4
        reasons.append("适合 Earth Signal 的长期议题 +4")

    return score, "；".join(reasons)


def select_best_story(candidates: list) -> tuple:
    scored = []
    for candidate in candidates:
        score, reason = score_candidate(candidate)
        enriched = candidate.copy()
        enriched["score"] = score
        enriched["reason"] = reason
        scored.append(enriched)
    scored.sort(key=lambda item: item["score"], reverse=True)
    selected = scored[0]
    selection = {
        "totalCandidates": len(candidates),
        "selectedScore": selected["score"],
        "selectedReason": selected["reason"],
        "topCandidates": [
            {
                "title": item["title"],
                "sourceName": item["sourceName"],
                "score": item["score"],
                "reason": item["reason"],
            }
            for item in scored[:5]
        ],
    }
    return selected, selection


def build_original_content(item: dict) -> dict:
    title = item["title"]
    summary = item["summary"]
    podcast_script = (
        "Hello, this is Earth Signal.\n\n"
        f"Today's story comes from {item['sourceName']}: {title}.\n\n"
        f"The report says: {summary}\n\n"
        "The signal is the longer trend behind the headline: how technology keeps moving into public life, infrastructure, science and everyday decisions."
    )
    ai_insight = (
        "The important signal is not just the event, but the system it points to: "
        "technology is becoming part of how societies manage risk, opportunity and trust."
    )
    return {
        "title": title,
        "summary": summary,
        "podcastScript": podcast_script,
        "aiInsight": ai_insight,
        "sourceUrl": item["sourceUrl"],
    }


def keyword_title(title: str, summary: str = "") -> str:
    text = f"{title} {summary}".lower()
    if "nasa" in text or "space" in text or "satellite" in text:
        return "太空与卫星技术释放新的地球观测信号"
    if "climate" in text or "environment" in text:
        return "气候与环境科技出现新的全球信号"
    if "energy" in text:
        return "能源科技变化正在影响城市与生活"
    if "ai" in text or "artificial intelligence" in text:
        return "人工智能新闻释放新的社会信号"
    if "robot" in text:
        return "机器人技术进入新的应用阶段"
    if "chip" in text:
        return "芯片行业出现新的竞争变化"
    if "health" in text:
        return "健康科技正在改变公共生活"
    words = [word for word in re.split(r"[^A-Za-z0-9]+", title) if word][:6]
    translated = [TERM_MAP.get(word.lower(), "") for word in words]
    translated = [word for word in translated if word]
    if translated:
        return "、".join(dict.fromkeys(translated)) + "成为今日科技焦点"
    return "一条科技新闻显示新的社会变化"


def summarize_in_chinese(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if "nasa" in text or "satellite" in text or "space" in text:
        return "这条新闻关注太空与卫星技术的新进展，它可能帮助人类更好理解地球、气候、灾害或未来探索。"
    if "climate" in text or "environment" in text:
        return "这条新闻关注气候与环境相关技术，背后牵动城市韧性、公共安全和长期生活方式变化。"
    if "energy" in text:
        return "这条新闻关注能源技术的新变化，背后关系到城市运行、成本压力和低碳转型。"
    if "ai" in text or "artificial intelligence" in text:
        return "这条新闻关注人工智能的新动作，背后反映技术扩张、公共规则和日常生活之间的关系。"
    if "health" in text:
        return "这条新闻关注健康科技或公共健康的新变化，它可能影响普通人获得服务和管理风险的方式。"
    return "这条新闻关注科技行业的新变化，背后涉及创新速度、公共信任和社会规则如何重新调整。"


def build_chinese_content(original_content: dict) -> dict:
    title = keyword_title(original_content["title"], original_content["summary"])
    summary = summarize_in_chinese(original_content["title"], original_content["summary"])
    content = {
        "title": title,
        "summary": summary[:80],
    }
    content["podcastScript"] = build_podcast_script_zh(content)
    content["aiInsight"] = build_ai_insight_zh(content)
    return content


def build_podcast_script_zh(chinese_content: dict) -> str:
    title = chinese_content["title"]
    summary = chinese_content["summary"]
    return (
        "今天的 Earth Signal 来自全球科技新闻现场。\n\n"
        f"我们关注的是：{title}。{summary}\n\n"
        "如果把它放在更长的时间线上看，这不只是一次技术更新。它说明科技正在更深地进入城市、公共服务、环境风险和普通人的日常选择。\n\n"
        "值得听的地方在于：真正改变生活的，往往不是某个单点发明，而是它和社会系统连接起来之后，开始重新分配效率、风险和机会。\n\n"
        "今天的信号是：技术越靠近地球，越需要被听见的不只是速度，还有它会把我们带向怎样的生活。"
    )


def build_ai_insight_zh(chinese_content: dict) -> str:
    text = chinese_content["title"] + chinese_content["summary"]
    if "气候" in text or "环境" in text or "卫星" in text or "太空" in text:
        return (
            "这条新闻真正指向的，是人类正在用更高维度的技术重新理解地球。"
            "当太空、气候和城市治理连在一起，科技就不只是远方的探索，也会变成每个人生活里的安全感。"
        )
    if "人工智能" in text:
        return (
            "人工智能的长期信号不只是模型更强，而是它正在进入社会运行的底层。"
            "普通人需要关注的，是技术如何参与决策，以及这些决策是否仍然能被理解和监督。"
        )
    if "能源" in text:
        return (
            "能源科技的变化往往不显眼，却会深刻影响城市成本、产业节奏和家庭生活。"
            "真正的信号，是低碳转型正在从口号变成基础设施的重新安排。"
        )
    return (
        "这条新闻背后的长期趋势，是科技越来越少停留在屏幕里，越来越多进入社会结构本身。"
        "它提醒我们，未来不是突然到来的，而是通过这些看似零散的新闻一点点靠近。"
    )


def build_audio_text(zh_content: dict) -> str:
    return (
        zh_content["podcastScript"]
        + "\n\n最后，给你今天的关键信号。\n\n"
        + zh_content["aiInsight"]
    )


async def generate_audio_from_zh(content: str) -> None:
    try:
        import edge_tts
    except ImportError:
        print("edge-tts is not installed.")
        print("Please run: python3 -m pip install edge-tts")
        raise SystemExit(1)

    output_file = Path(__file__).resolve().parent / AUDIO_PATH
    output_file.parent.mkdir(exist_ok=True)
    communicate = edge_tts.Communicate(content, voice=VOICE, rate="+0%")
    await communicate.save(str(output_file))


def save_json(data: dict) -> Path:
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(exist_ok=True)
    json_file = data_dir / "today-podcast.json"
    json_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_file


async def main() -> None:
    item = fetch_rss_item()
    original = build_original_content(item)
    zh = build_chinese_content(original)
    payload = {
        "date": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d"),
        "region": "GLOBAL",
        "category": item["category"],
        "sourceName": item["sourceName"],
        "sourceUrl": original["sourceUrl"],
        "language": {
            "original": "en",
            "default": "zh",
        },
        "original": {
            "title": original["title"],
            "summary": original["summary"],
            "podcastScript": original["podcastScript"],
            "aiInsight": original["aiInsight"],
        },
        "zh": zh,
        "audio": {
            "src": AUDIO_PATH,
            "duration": "01:00",
        },
        "selection": item["selection"],
    }

    json_file = save_json(payload)
    await generate_audio_from_zh(build_audio_text(zh))

    print(f"Generated {json_file}")
    print(f"Generated {Path(__file__).resolve().parent / AUDIO_PATH}")
    print(f"Candidates: {payload['selection']['totalCandidates']}")
    print(f"Selected: {payload['original']['title']}")
    print(f"Score: {payload['selection']['selectedScore']}")
    print(f"Reason: {payload['selection']['selectedReason']}")
    print(f"Source: {payload['sourceUrl']}")


if __name__ == "__main__":
    asyncio.run(main())
