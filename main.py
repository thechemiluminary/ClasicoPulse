"""
ClasicoPulse - orchestrator.

Two entry points (run by clasico.yml on a 5-minute cron-job):
  python main.py --pump     -> process any pending Telegram button presses
                               (Approve -> publish to FB, Decline/Done -> drop)
  python main.py --collect  -> pull recent channel posts; send photo/text posts as
                               Approve/Decline drafts, video posts as manual alerts
"""
import datetime
import json
import sys

import config
import store
import publisher
import telegram_bot as tg


def _pump_one(cq, state):
    """Handle a single callback_query (appr/decl/done). Never crashes the run -
    any failure answers the button with the real error instead of going silent."""
    data = cq.get("data", "")
    action, _, pid = data.partition(":")
    if not pid:
        return
    try:
        chat_id = cq["message"]["chat"]["id"]
        msg_id = cq["message"]["message_id"]
    except Exception:
        chat_id, msg_id = None, None
    qid = cq["id"]

    if action == "appr":
        entry = store.get_pending(state, pid)
        if not entry:
            tg.answer(qid, "Already processed / expired ⏳")
            if chat_id and msg_id:
                tg.clear_buttons(chat_id, msg_id)
            return
        try:
            ok, detail = publisher.publish_entry(entry)
        except Exception as e:
            ok, detail = False, f"exception: {e}"
        store.remove_pending(state, pid)
        if ok:
            store.mark_posted(state, pid, detail)
            tg.answer(qid, "✅ Posted to ClasicoPulse")
        else:
            store.mark_declined(state, pid)
            tg.answer(qid, f"❌ Publish failed: {detail}")
        if chat_id and msg_id:
            tg.clear_buttons(chat_id, msg_id)
        print(f"[pump] {action} {pid} -> {'posted:' + detail if ok else 'failed:' + str(detail)}")

    elif action == "decl":
        store.remove_pending(state, pid)
        store.mark_declined(state, pid)
        tg.answer(qid, "Declined 🚫")
        if chat_id and msg_id:
            tg.clear_buttons(chat_id, msg_id)
        print(f"[pump] declined {pid}")

    elif action == "done":
        store.mark_alerted(state, pid)
        tg.answer(qid, "Noted ✅ post it whenever you're ready")
        if chat_id and msg_id:
            tg.clear_buttons(chat_id, msg_id)
        print(f"[pump] done {pid}")


def run_pump():
    state = store.load()
    offset = store.get_offset(state)
    callbacks, offset = tg.poll_callbacks(offset)
    for cq in callbacks:
        _pump_one(cq, state)
    store.set_offset(state, offset)
    dropped = store.prune_expired(state)
    store.save(state)
    return {"status": "done", "processed": len(callbacks), "expired_pending": dropped}


def run_collect():
    state = store.load()
    drafts, alerts, ads = 0, 0, 0
    pending_count = len(state["pending"])
    for ch in config.TELEGRAM_CHANNELS:
        ch = ch.strip()
        if not ch:
            continue
        from collector import collect, is_ad
        posts = collect(ch)
        print(f"[collect] {ch}: {len(posts)} posts parsed")
        for post in posts:
            pid = post["post_id"]
            if store.is_seen(state, pid):
                continue

            if is_ad(post):
                store.mark_seen(state, pid, "ad")
                store.mark_ads(state, pid)
                ads += 1
                print(f"[collect] skip ad {pid}")
                continue

            if post["kind"] in ("video", "unsupported"):
                if config.DRY_RUN:
                    print(f"[collect] DRY_RUN would alert video {pid}")
                    store.mark_seen(state, pid, "video")
                    alerts += 1
                    continue
                ok, _ = tg.send_video_alert(post)
                if ok:
                    store.mark_seen(state, pid, "video")
                    store.mark_alerted(state, pid)
                    alerts += 1
                else:
                    print(f"[collect] video alert send failed {pid} (retry next run)")
                continue

            # Publishable post (photo/text) -> Approve/Decline draft.
            if drafts >= config.MAX_DRAFTS_PER_RUN or pending_count >= config.PENDING_MAX:
                print(f"[collect] draft cap hit ({drafts}/{config.MAX_DRAFTS_PER_RUN}, "
                      f"pending={pending_count}) - stopping")
                store.save(state)
                return {"status": "done", "drafts": drafts, "alerts": alerts, "ads": ads,
                        "cap_hit": True}

            if config.DRY_RUN:
                print(f"[collect] DRY_RUN would draft {pid} ({post['kind']})")
                store.mark_seen(state, pid, post["kind"])
                drafts += 1
                continue

            ok, _ = tg.send_draft(post)
            if ok:
                store.add_pending(state, post)
                store.mark_seen(state, pid, post["kind"])
                pending_count += 1
                drafts += 1
                print(f"[collect] draft sent {pid} ({post['kind']})")
            else:
                print(f"[collect] draft send failed {pid} (retry next run)")

    store.prune_expired(state)
    store.save(state)
    print(f"[collect] done: {drafts} drafts, {alerts} alerts, {ads} ads skipped")
    return {"status": "done", "drafts": drafts, "alerts": alerts, "ads": ads}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--pump":
        print(json.dumps(run_pump(), ensure_ascii=False, default=str))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--collect":
        print(json.dumps(run_collect(), ensure_ascii=False, default=str))
        sys.exit(0)
    print("usage: main.py --pump | --collect")
    sys.exit(1)