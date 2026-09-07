"""
ClasicoPulse - durable state store (state.json, committed to the repo each run).

Schema:
{
  "seen":     { "CH/post_id": {at_utc, kind} },          # ever sent (draft OR alert) - no re-send
  "pending":  { post_id: {post_id, channel, caption, photos[], post_url, kind, created_utc} },
  "posted":   { post_id: {fb_post_id, at_utc} },
  "declined": { post_id: {at_utc} },
  "alerts":   { post_id: {at_utc} },                     # video/unsupported alerts sent
  "ads":      { post_id: {at_utc} },                     # auto-skipped sponsor posts
  "tg_update_offset": 0,
}
"""
import datetime
import json
import os

import config

_EMPTY = {
    "seen": {},
    "pending": {},
    "posted": {},
    "declined": {},
    "alerts": {},
    "ads": {},
    "tg_update_offset": 0,
}


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load():
    if not os.path.exists(config.STATE_PATH):
        return dict(_EMPTY)
    try:
        with open(config.STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(_EMPTY)


def save(state):
    """Atomic write so a killed run never corrupts the file."""
    tmp = config.STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, config.STATE_PATH)


# --- seen ---

def is_seen(state, post_id):
    return post_id in state["seen"]


def mark_seen(state, post_id, kind):
    state["seen"][post_id] = {"at_utc": _utcnow(), "kind": kind}


# --- pending approvals ---

def add_pending(state, entry):
    state["pending"][entry["post_id"]] = dict(entry, created_utc=_utcnow())


def get_pending(state, post_id):
    return state["pending"].get(post_id)


def remove_pending(state, post_id):
    return state["pending"].pop(post_id, None)


def prune_expired(state):
    """Drop pending approvals older than PENDING_TTL_HOURS."""
    if not state["pending"]:
        return 0
    keep, dropped = {}, 0
    now = datetime.datetime.now(datetime.timezone.utc)
    for pid, e in state["pending"].items():
        try:
            created = datetime.datetime.fromisoformat(e.get("created_utc", ""))
            if created < now - datetime.timedelta(hours=config.PENDING_TTL_HOURS):
                dropped += 1
                continue
        except Exception:
            pass
        keep[pid] = e
    state["pending"] = keep
    return dropped


# --- results ---

def mark_posted(state, post_id, fb_post_id):
    state["posted"][post_id] = {"fb_post_id": fb_post_id, "at_utc": _utcnow()}


def mark_declined(state, post_id):
    state["declined"][post_id] = {"at_utc": _utcnow()}


def mark_alerted(state, post_id):
    state["alerts"][post_id] = {"at_utc": _utcnow()}


def mark_ads(state, post_id):
    state["ads"][post_id] = {"at_utc": _utcnow()}


# --- telegram update offset ---

def get_offset(state):
    return int(state.get("tg_update_offset", 0))


def set_offset(state, offset):
    state["tg_update_offset"] = int(offset)