"""
ClasicoPulse - Configuration.
FC Barcelona + Real Madrid news reposter. All secrets come from environment
variables at runtime (never hardcoded).
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Facebook page (new ClasicoPulse page; same Meta app as WeekendPulse) ---
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
GRAPH_BASE = os.environ.get("GRAPH_BASE", "https://graph.facebook.com/v26.0")

# --- Telegram bot (new bot) + your chat ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")
TG_API = "https://api.telegram.org/bot" + (TG_BOT_TOKEN or "TOKEN")
# Long-poll timeout seconds for getUpdates (max allowed by Telegram is 50).
POLL_TIMEOUT = int(os.environ.get("POLL_TIMEOUT", "30"))

# --- Source channels (public username channels, fetched via t.me/s/<ch>) ---
TELEGRAM_CHANNELS = os.environ.get("TELEGRAM_CHANNELS", "Barca_Studio_News").split(",")

# --- Behaviour ---
MAX_DRAFTS_PER_RUN = int(os.environ.get("MAX_DRAFTS_PER_RUN", "5"))  # approve drafts / run
PENDING_MAX = int(os.environ.get("PENDING_MAX", "20"))                # max bundled approvals awaiting your click
COLLECT_LIMIT = int(os.environ.get("COLLECT_LIMIT", "20"))            # newest messages parsed
PENDING_TTL_HOURS = int(os.environ.get("PENDING_TTL_HOURS", "24"))    # pending approvals expire
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

# --- Caption -------------------------------------------------------------
# Append a credit line to every posted caption. Empty string to disable.
CREDIT_TEXT = os.environ.get("CREDIT_TEXT", "عبر @{channel}")


def build_caption(caption, channel):
    """Full Facebook caption = cleaned source text + optional credit line."""
    t = (caption or "").strip()
    credit = CREDIT_TEXT.format(channel=channel)
    if credit:
        t = (t + "\n\n" + credit).strip() if t else credit
    return t


# --- Ad / sponsor filter ------------------------------------------------
# Posts matching any of these substrings are auto-skipped (
# the channel runs paid sponsor posts between football news).
AD_KEYWORDS = [
    k.strip() for k in os.environ.get(
        "AD_KEYWORDS", "للإعلانات,إعلان,مساحة إعلانية,رابط القناة,تواصل معنا"
    ).split(",") if k.strip()
]

# --- Paths ---
STATE_PATH = os.path.join(BASE_DIR, "state.json")
MEDIA_DIR = os.path.join(BASE_DIR, "data", "media")