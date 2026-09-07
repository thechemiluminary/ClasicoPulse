"""
ClasicoPulse - collector.

Fetches recent posts of public Telegram channels via their web preview
(t.me/s/<channel>) and parses each post into:
    {post_id, channel, caption, photos[], post_url, kind, timestamp}
where kind is:
    "photo"       -> has photo URL(s)      -> publishable to FB
    "text"        -> caption only          -> publishable to FB
    "video"       -> video marker (no file downloadable from t.me/s) -> ALERT
    "unsupported" -> media we can't link   -> ALERT

Photos render as direct https://cdn4.telesco.pe/...jpg URLs (no auth needed).
Videos/mp4s never appear on the preview page, so they are alerted instead of
being silently skipped.
"""
import datetime
import html
import re
import urllib.parse
import urllib.request

import requests

import config

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en",
}

_PHOTO = re.compile(
    r"class=\"tgme_widget_message_photo_wrap[^\"]*\"[^>]*background-image:url\('([^']+)'\)"
)
_CAPTION = re.compile(
    r'<div class="tgme_widget_message_text js-message_text"[^>]*>(.*?)</div>', re.S
)
_VIDEO = re.compile(r"tgme_widget_message_video|<video|js-message_video")
_TIME = re.compile(r'<time datetime="([^"]+)"')


def _caption_clean(html_frag):
    if not html_frag:
        return ""
    t = html_frag
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def _looks_ad(caption, keywords):
    c = caption or ""
    return any(k and k in c for k in keywords)


def fetch_html(channel):
    url = f"https://t.me/s/{channel}"
    try:
        r = requests.get(url, headers=_UA, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"[collect] fetch failed {channel}: {e}")
        return ""


def parse_posts(html_page, channel):
    """Return a list of parsed post dicts from a t.me/s page (page order)."""
    if not html_page:
        return []
    split_pat = re.compile(
        r'<div class="tgme_widget_message[^"]*"[^>]*?data-post="'
        + re.escape(channel) + r'/(\d+)"'
    )
    raw = [b.strip() for b in split_pat.split(html_page)]
    # raw[0] is preamble; then alternating (id, body html) pairs.
    posts = []
    for i in range(1, len(raw) - 1, 2):
        post_id = raw[i]
        body = raw[i + 1]
        caption = _caption_clean(_CAPTION.search(body).group(1) if _CAPTION.search(body) else "")
        photos = _PHOTO.findall(body)
        is_video = bool(_VIDEO.search(body))
        ts = ""
        m = _TIME.search(body)
        if m:
            ts = m.group(1)
        if is_video:
            kind = "video"
        elif photos:
            kind = "photo"
        elif caption:
            kind = "text"
        else:
            kind = "unsupported"
        posts.append({
            "post_id": f"{channel}/{post_id}",
            "channel": channel,
            "caption": caption,
            "photos": photos,
            "post_url": f"https://t.me/{channel}/{post_id}",
            "kind": kind,
            "timestamp": ts,
        })
    return posts


def collect(channel, limit=config.COLLECT_LIMIT):
    """Collect the newest `limit` posts from a channel (newest first)."""
    posts = parse_posts(fetch_html(channel), channel)
    posts.sort(key=lambda p: p["timestamp"] or "", reverse=True)
    return posts[:limit]


def is_ad(post, keywords=config.AD_KEYWORDS):
    return _looks_ad(post.get("caption"), keywords)