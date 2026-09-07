"""
ClasicoPulse - Facebook publisher (photo + text posts to the Page via Graph API).
Ported from the WeekendPulse publisher (sanitize_text fix included).
"""
import requests

import config

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ClasicoPulse bot/1.0"


def sanitize_text(text):
    """
    Normalize text so it is always valid UTF-8 for the Graph upload encoding.
    A UTF-16 round-trip (with surrogatepass) combines valid high+low surrogate
    pairs back into a single astral char and replaces stray lone surrogates.
    """
    if not isinstance(text, str):
        return text
    return text.encode("utf-16", errors="surrogatepass").decode("utf-16", errors="replace")


def _headers():
    if not config.FB_PAGE_TOKEN:
        raise RuntimeError("FB_PAGE_TOKEN not set")
    return {"Authorization": f"Bearer {config.FB_PAGE_TOKEN}"}


def post_text(message):
    """Publish a text-only post. Returns (ok, post_id_or_error)."""
    url = f"{config.GRAPH_BASE}/{config.FB_PAGE_ID}/feed"
    try:
        r = requests.post(
            url, json={"message": sanitize_text(message)}, headers=_headers(), timeout=60)
        j = r.json()
    except Exception as e:
        return False, f"request failed: {e}"
    if r.status_code == 200 and j.get("id"):
        return True, j["id"]
    return False, j


def _download(url, timeout=60):
    r = requests.get(url, timeout=timeout, headers={"User-Agent": _UA})
    r.raise_for_status()
    return r.content


def post_photo(message, photo_url):
    """Download the channel photo and publish it with caption. Returns (ok, result)."""
    try:
        content = _download(photo_url)
    except Exception as e:
        return False, f"photo download failed: {e}"
    if not content:
        return False, "photo download returned empty"
    url = f"{config.GRAPH_BASE}/{config.FB_PAGE_ID}/photos"
    try:
        r = requests.post(
            url,
            data={"message": sanitize_text(message)},
            files={"source": content},
            headers=_headers(),
            timeout=120)
        j = r.json()
    except Exception as e:
        return False, f"request failed: {e}"
    if r.status_code == 200 and (j.get("id") or j.get("post_id")):
        return True, j.get("post_id") or j.get("id")
    return False, j


def publish_entry(entry):
    """
    Publish a stored pending entry (caption + optional photo) to the Page.
    Falls back to text-only if the photo fails. Returns (ok, detail).
    """
    caption = sanitize_text(config.build_caption(entry.get("caption"), entry.get("channel")))
    photos = entry.get("photos") or []
    if entry.get("kind") == "photo" and photos:
        ok, res = post_photo(caption, photos[0])
        if ok:
            return True, f"photo:{res}"
        print(f"[publish] photo failed ({res}); falling back to text")
    return post_text(caption)