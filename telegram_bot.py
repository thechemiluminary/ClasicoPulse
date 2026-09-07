"""
ClasicoPulse - Telegram bot (drafts with Approve/Decline buttons + video alerts
+ callback pump).

The bot does NOT run 24/7. Every 5-min workflow run polls getUpdates once, so
a button press is answered within one cron cycle (max ~5 min latency). No
always-on server required.
"""
import requests

import config

MAX_PREVIEW = 1500  # draft preview length in Telegram (full caption is kept for FB)


def _api(method, params):
    """Call Telegram Bot API. Returns (ok, json_result)."""
    if not config.TG_BOT_TOKEN:
        return False, "TG_BOT_TOKEN not set"
    try:
        r = requests.post(f"{config.TG_API}/{method}", json=params, timeout=60)
        j = r.json()
        return bool(j.get("ok")), j
    except Exception as e:
        return False, str(e)


def _trunc(text, n=MAX_PREVIEW):
    t = (text or "").strip()
    return t if len(t) <= n else t[: n - 3] + "..."


def _preview_text(entry):
    txt = _trunc(entry.get("caption", ""))
    txt = (txt + f"\n\n🔗 {entry['post_url']}").strip() if txt else entry["post_url"]
    return txt


def send_draft(entry):
    """Send a photo/text post as an Approve/Decline draft."""
    buttons = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"appr:{entry['post_id']}"},
            {"text": "❌ Decline", "callback_data": f"decl:{entry['post_id']}"},
        ]]
    }
    return _api("sendMessage", {
        "chat_id": config.TG_CHAT_ID,
        "text": _preview_text(entry),
        "reply_markup": buttons,
        "disable_web_page_preview": False,
    })


def send_video_alert(entry):
    """Alert the user that a video/unsupported post needs MANUAL posting."""
    caption = _trunc(entry.get("caption", ""), 300)
    text = f"🎬 Video post — post it manually:\n{entry['post_url']}"
    if caption:
        text += f"\n\n{caption}"
    buttons = {
        "inline_keyboard": [[
            {"text": "✅ Done", "callback_data": f"done:{entry['post_id']}"},
        ]]
    }
    return _api("sendMessage", {
        "chat_id": config.TG_CHAT_ID,
        "text": text,
        "reply_markup": buttons,
        "disable_web_page_preview": False,
    })


def send_text(text):
    return _api("sendMessage", {"chat_id": config.TG_CHAT_ID, "text": text})


def answer(query_id, text):
    """Dismiss the loading spinner on the pressed button."""
    return _api("answerCallbackQuery", {
        "callback_query_id": query_id,
        "text": text or "",
    })


def clear_buttons(chat_id, message_id):
    """Remove the Approve/Decline/Done buttons after the user decided."""
    return _api("editMessageReplyMarkup", {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": []},
    })


def poll_callbacks(offset=0):
    """
    Poll for pending updates. Returns (callbacks, new_offset).

    Polls ALL update types (no allowed_updates filter) and always advances the
    offset past every update. Telegram delivers updates strictly in order, so
    filtering with allowed_updates ["callback_query"] can jam callbacks behind
    the user's own unconsumed message updates (e.g. the very first /start).
    Skipping-but-confirming every update type keeps the queue from blocking.
    """
    callbacks = []
    if not config.TG_BOT_TOKEN:
        return callbacks, int(offset)
    params = {"timeout": config.POLL_TIMEOUT, "offset": int(offset)}
    ok, j = _api("getUpdates", params)
    if not ok:
        return callbacks, int(offset)
    for u in j.get("result", []):
        offset = int(u["update_id"]) + 1
        cq = u.get("callback_query")
        if cq:
            callbacks.append(cq)
    return callbacks, int(offset)