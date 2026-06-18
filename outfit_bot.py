#!/usr/bin/env python3
"""
WIS Outfit Bot — Telegram bot for OOTD outfit logging.

Send a mirror selfie → AI identifies items → review queue → Notion entry created.

Commands:
    /start       — welcome
    /date YYYY-MM-DD — override date for next outfit
    /refresh     — force-refresh collection cache
    /help        — command list
"""

import os, sys, base64, asyncio, traceback, json, hashlib
from io import BytesIO
from datetime import date
from pathlib import Path
from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from PIL import Image
from PIL.ExifTags import TAGS
from dotenv import load_dotenv

load_dotenv()

import collection_cache
import vision_matcher
import notion_writer
import corrections_db
import lookbook as lookbook_mod

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# ── Always-worn items ─────────────────────────────────────────────────────────
ALWAYS_WORN_FILE = Path(__file__).parent / "always_worn.json"

def _load_always_worn() -> list[dict]:
    """Load always-worn item list from config file."""
    try:
        data = json.loads(ALWAYS_WORN_FILE.read_text())
        return data.get("items", [])
    except Exception:
        return []

def _save_always_worn(items: list[dict]):
    data = json.loads(ALWAYS_WORN_FILE.read_text()) if ALWAYS_WORN_FILE.exists() else {}
    data["items"] = items
    ALWAYS_WORN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def _always_worn_as_decisions(catalog: list[dict]) -> list[dict]:
    """
    Build pre-approved decision dicts for each always-worn item.
    Returns list of decisions ready to prepend to the session's decisions list.
    """
    always = _load_always_worn()
    decisions = []
    for aw in always:
        item_id = aw["id"]
        item = next((c for c in catalog if c["id"] == item_id), None)
        if item:
            decisions.append({
                "action": "approved",
                "item_id": item_id,
                "item_name": item["name"],
                "always_worn": True,
            })
    return decisions

# ── Per-user session state ────────────────────────────────────────────────────
_sessions: dict[int, dict] = {}
_date_override: dict[int, str] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _notion_url(item: dict) -> str:
    clean_id = item["id"].replace("-", "")
    return f"https://www.notion.so/{clean_id}"


def _extract_exif_date(image_bytes: bytes) -> str | None:
    try:
        img = Image.open(BytesIO(image_bytes))
        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "DateTimeOriginal":
                    from datetime import datetime
                    dt = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                    return dt.date().isoformat()
    except Exception:
        pass
    return None


def _resize_for_vision(image_bytes: bytes, max_dim=1600) -> bytes:
    img = Image.open(BytesIO(image_bytes))
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _status_emoji(status: str) -> str:
    return {"matched": "✅", "ambiguous": "⚠️", "unidentified": "❓"}.get(status, "•")


def _esc(text: str) -> str:
    """HTML-escape text for Telegram HTML parse mode."""
    return escape(str(text))


def _build_item_card(result: dict, idx: int, total: int, decision: dict | None = None) -> tuple[str, InlineKeyboardMarkup]:
    ident = result["identified"]
    status = result["status"]
    emoji = _status_emoji(status)
    top = result["top_matches"]

    memory_tag = " 🧠" if result.get("from_memory") else ""
    lines = [f"<b>Item {idx + 1} of {total}</b> {emoji}{memory_tag}"]
    lines.append(f"<i>{_esc(ident['type'].title())} — {_esc(ident['colour'])}</i>")
    lines.append(f"{_esc(ident['description'][:120])}")
    lines.append("")

    if top:
        best = top[0]
        item = best["item"]
        conf_pct = int(best["confidence"] * 100)
        url = _notion_url(item)
        designer = item.get("designer", "")
        colour = item.get("colour", "")
        lines.append(f"<b>Best match ({conf_pct}%):</b>")
        lines.append(f'<a href="{url}">{_esc(item["name"])}</a>')
        if designer:
            lines.append(f"  {_esc(designer)}")
        if colour:
            lines.append(f"  {_esc(colour)}")
        lines.append(f"  <code>{_esc(item['sku'])}</code>")
        if len(top) > 1:
            alt = top[1]
            alt_item = alt["item"]
            alt_url = _notion_url(alt_item)
            lines.append(f'\n<i>Alt ({int(alt["confidence"]*100)}%): <a href="{alt_url}">{_esc(alt_item["name"])}</a></i>')
    else:
        lines.append("<i>No match found in collection</i>")

    if decision:
        action = decision["action"]
        if action == "approved":
            lines.append(f"\n✅ <b>Approved</b>")
        elif action == "skipped":
            lines.append(f"\n⏭️ <b>Skipped</b>")
        elif action == "changed":
            lines.append(f"\n✏️ Changed to: {_esc(decision.get('item_name', '?'))}")

    text = "\n".join(lines)

    buttons = []
    if not decision:
        if top:
            # Has a match — show approve
            row1 = [
                InlineKeyboardButton("✅ Correct", callback_data=f"approve:{idx}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{idx}"),
            ]
            buttons.append(row1)
            if len(top) > 1:
                alt_item = top[1]["item"]
                buttons.append([
                    InlineKeyboardButton(
                        f"↕️ Use: {alt_item['name'][:28]}",
                        callback_data=f"alt:{idx}",
                    )
                ])
        else:
            # No match — only skip or search
            buttons.append([InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{idx}")])

        buttons.append([InlineKeyboardButton("🔍 Search collection", callback_data=f"search:{idx}")])

    return text, InlineKeyboardMarkup(buttons) if buttons else InlineKeyboardMarkup([])


def _build_summary(session: dict) -> str:
    results = session["results"]
    decisions = session["decisions"]
    always = session.get("always_worn_decisions", [])

    approved = [(r, d) for r, d in zip(results, decisions) if d and d["action"] in ("approved", "changed")]
    skipped = [r for r, d in zip(results, decisions) if d and d["action"] == "skipped"]

    lines = ["<b>Review Summary</b>\n"]

    # Always-worn items first
    if always:
        for d in always:
            item_id = d.get("item_id", "")
            url = f"https://www.notion.so/{item_id.replace('-', '')}"
            lines.append(f'💍 <a href="{url}">{_esc(d["item_name"])}</a> <i>(daily)</i>')

    for r, d in approved:
        item_name = d.get("item_name") or r["top_matches"][0]["item"]["name"]
        item_id = d.get("item_id", "")
        if item_id:
            url = f"https://www.notion.so/{item_id.replace('-', '')}"
            lines.append(f'✅ <a href="{url}">{_esc(item_name)}</a>')
        else:
            lines.append(f"✅ {_esc(item_name)}")
    for r in skipped:
        lines.append(f"⏭️ <i>{_esc(r['identified']['type'])} — skipped</i>")

    total = len(always) + len(approved)
    lines.append(f"\n<b>Date:</b> {session['date']}")
    lines.append(f"<b>Items to link:</b> {total}")
    return "\n".join(lines)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>WIS Outfit Bot</b>\n\n"
        "Send me a mirror selfie and I'll identify what you're wearing, "
        "match items to your collection, and log the outfit to Notion.\n\n"
        "Commands:\n"
        "/date YYYY-MM-DD — override date for next outfit\n"
        "/refresh — reload collection cache\n"
        "/help — this message",
        parse_mode=ParseMode.HTML,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        current = _date_override.get(user_id, "not set (using EXIF or today)")
        await update.message.reply_text(f"Current date override: {current}\n\nUsage: /date YYYY-MM-DD")
        return
    date_str = args[0]
    try:
        date.fromisoformat(date_str)
        _date_override[user_id] = date_str
        await update.message.reply_text(
            f"Date override set: <b>{date_str}</b>\nSend your outfit photo.",
            parse_mode=ParseMode.HTML,
        )
    except ValueError:
        await update.message.reply_text("Invalid date. Use format: YYYY-MM-DD (e.g. /date 2026-06-15)")


async def cmd_always(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /always           — list current always-worn items
    /always add <query> — search and add an item
    /always remove <query> — remove an item by name
    /always clear     — remove all
    """
    args = context.args
    catalog = collection_cache.load()

    if not args or args[0] == "list":
        items = _load_always_worn()
        if not items:
            await update.message.reply_text(
                "No always-worn items set.\n\nUse /always add <search> to add one.\nE.g. /always add cartier necklace"
            )
            return
        lines = ["<b>Always-worn items (added to every OOTD):</b>\n"]
        for i, aw in enumerate(items, 1):
            url = f"https://www.notion.so/{aw['id'].replace('-', '')}"
            lines.append(f'{i}. <a href="{url}">{_esc(aw["name"])}</a>')
        lines.append("\n/always add &lt;search&gt; — add item\n/always remove &lt;name&gt; — remove item")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    if args[0] == "clear":
        _save_always_worn([])
        await update.message.reply_text("Always-worn list cleared.")
        return

    if args[0] == "add":
        query = " ".join(args[1:]).lower()
        if not query:
            await update.message.reply_text("Usage: /always add <search term>")
            return
        matches = [
            c for c in catalog
            if query in c["name"].lower() or query in c.get("designer", "").lower()
        ][:6]
        if not matches:
            await update.message.reply_text(f"No items found for '{query}'.")
            return
        buttons = [
            [InlineKeyboardButton(
                f"{m['name'][:40]} ({m.get('designer', '')[:12]})",
                callback_data=f"always_add:{m['id']}"
            )]
            for m in matches
        ]
        await update.message.reply_text(
            f"Select item to always include:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if args[0] == "remove":
        query = " ".join(args[1:]).lower()
        items = _load_always_worn()
        new_items = [i for i in items if query not in i["name"].lower()]
        removed = len(items) - len(new_items)
        _save_always_worn(new_items)
        await update.message.reply_text(f"Removed {removed} item(s). Use /always to see current list.")
        return

    await update.message.reply_text("Usage: /always | /always add <search> | /always remove <name> | /always clear")


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Refreshing collection cache...")
    try:
        items = collection_cache.refresh()
        await msg.edit_text(f"Cache refreshed. {len(items)} items loaded.")
    except Exception as e:
        await msg.edit_text(f"Refresh failed: {e}")


# ── Pending images (waiting for date confirmation) ────────────────────────────
# user_id → {all_images: [bytes], img_hash: str}
_pending: dict[int, dict] = {}

# ── Media group buffer (collecting album photos before processing) ─────────────
# media_group_id → {update, all_images: [bytes], task: asyncio.Task}
_media_groups: dict[str, dict] = {}

ALBUM_COLLECT_SECS = 3  # wait this long after first photo before processing album


async def _flush_album(media_group_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Called after ALBUM_COLLECT_SECS — process all buffered album images."""
    await asyncio.sleep(ALBUM_COLLECT_SECS)
    data = _media_groups.pop(media_group_id, None)
    if not data:
        return
    print(f"[album] flushing {len(data['all_images'])} images for group {media_group_id}", flush=True)
    await _process_images(data["update"], context, data["all_images"])


async def _download_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bytes:
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    buf = BytesIO()
    await file.download_to_memory(buf)
    return buf.getvalue()


async def _download_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bytes | None:
    doc = update.message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        return None
    file = await context.bot.get_file(doc.file_id)
    buf = BytesIO()
    await file.download_to_memory(buf)
    return buf.getvalue()


# ── Photo + Document handlers ─────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mgid = update.message.media_group_id
    raw = await _download_photo(update, context)

    if mgid:
        # Part of an album — buffer and wait for siblings
        if mgid not in _media_groups:
            print(f"[album] started {mgid}", flush=True)
            task = asyncio.create_task(_flush_album(mgid, context))
            _media_groups[mgid] = {"update": update, "all_images": [raw], "task": task}
        else:
            _media_groups[mgid]["all_images"].append(raw)
    else:
        print(f"[photo] single from user {user_id}", flush=True)
        await _process_images(update, context, [raw])


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = await _download_document(update, context)
    if raw is None:
        return
    user_id = update.effective_user.id
    mgid = update.message.media_group_id

    if mgid:
        if mgid not in _media_groups:
            task = asyncio.create_task(_flush_album(mgid, context))
            _media_groups[mgid] = {"update": update, "all_images": [raw], "task": task}
        else:
            _media_groups[mgid]["all_images"].append(raw)
    else:
        print(f"[document] single from user {user_id}", flush=True)
        await _process_images(update, context, [raw])


async def _process_images(update: Update, context: ContextTypes.DEFAULT_TYPE, all_images: list[bytes]):
    """
    Entry point after all images for an outfit are collected.
    Uses first image for AI matching and EXIF; all images uploaded to Notion.
    """
    user_id = update.effective_user.id
    primary = all_images[0]
    img_hash = hashlib.sha256(primary).hexdigest()

    n = len(all_images)
    label = f"📸 {n} photo{'s' if n > 1 else ''} received."

    # ── Date resolution ───────────────────────────────────────────────────────
    if user_id in _date_override:
        outfit_date = _date_override.pop(user_id)
        msg = await update.message.reply_text(
            f"{label}\n📅 <b>{outfit_date}</b> <i>(set manually)</i>",
            parse_mode=ParseMode.HTML,
        )
        await _run_ai_and_review(update, context, all_images, img_hash, outfit_date, status_msg=msg)
        return

    exif_date = _extract_exif_date(primary)
    if exif_date:
        msg = await update.message.reply_text(
            f"{label}\n📅 <b>{exif_date}</b> <i>(from image metadata)</i>",
            parse_mode=ParseMode.HTML,
        )
        await _run_ai_and_review(update, context, all_images, img_hash, exif_date, status_msg=msg)
    else:
        # No EXIF — show date picker, hold images in pending
        _pending[user_id] = {"all_images": all_images, "img_hash": img_hash}

        from datetime import timedelta
        today = date.today()
        options = [
            (today.isoformat(), "Today"),
            ((today - timedelta(days=1)).isoformat(), "Yesterday"),
            ((today - timedelta(days=2)).isoformat(), (today - timedelta(days=2)).strftime("%a %-d %b")),
            ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=3)).strftime("%a %-d %b")),
        ]
        buttons = [
            [InlineKeyboardButton(lbl, callback_data=f"setdate:{iso}")]
            for iso, lbl in options
        ] + [[InlineKeyboardButton("📅 Pick a date", callback_data="setdate:pick")]]

        note = (
            f"{label}\n"
            "⚠️ <i>No date in image metadata (Telegram stripped it).\n"
            "Send as a <b>file</b> next time to preserve the date.</i>\n\n"
            "<b>When was this worn?</b>"
        )
        await update.message.reply_text(note, parse_mode=ParseMode.HTML,
                                         reply_markup=InlineKeyboardMarkup(buttons))


async def _run_ai_and_review(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    all_images: list[bytes],
    img_hash: str,
    outfit_date: str,
    status_msg=None,
):
    """Run AI matching on primary image, then start review flow."""
    user_id = update.effective_user.id
    eff_msg = update.effective_message
    msg = status_msg or await eff_msg.reply_text("🔍 Identifying items...")
    await msg.edit_text(
        f"📅 <b>{outfit_date}</b>\n\n🔍 Identifying items...",
        parse_mode=ParseMode.HTML,
    )

    try:
        catalog = collection_cache.load()
    except Exception as e:
        await msg.edit_text(f"Failed to load collection: {e}")
        return

    primary_resized = _resize_for_vision(all_images[0])
    image_b64 = base64.standard_b64encode(primary_resized).decode()

    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None, vision_matcher.run_matching, image_b64, catalog, img_hash
        )
    except Exception as e:
        await msg.edit_text(f"AI matching failed: {e}")
        print(f"run_matching error: {traceback.format_exc()}", file=sys.stderr)
        return

    if not results:
        await msg.edit_text("Could not identify any items. Try a clearer photo.")
        return

    always_decisions = _always_worn_as_decisions(catalog)
    n = len(all_images)

    _sessions[user_id] = {
        "all_images": all_images,         # all photos in the album
        "img_hash": img_hash,
        "date": outfit_date,
        "results": results,
        "decisions": [None] * len(results),
        "always_worn_decisions": always_decisions,
    }

    matched = sum(1 for r in results if r["status"] == "matched")
    ambiguous = sum(1 for r in results if r["status"] == "ambiguous")
    unidentified = sum(1 for r in results if r["status"] == "unidentified")
    photo_note = f" · {n} photos" if n > 1 else ""

    await msg.edit_text(
        f"📅 <b>{outfit_date}</b>{photo_note} · Found <b>{len(results)} item(s)</b> — "
        f"{matched} matched, {ambiguous} ambiguous, {unidentified} unidentified.",
        parse_mode=ParseMode.HTML,
    )
    await _show_next_item(eff_msg, _sessions[user_id], user_id)


async def _show_next_item(message, session: dict, user_id: int):
    results = session["results"]
    decisions = session["decisions"]

    for idx in range(len(results)):
        if decisions[idx] is None:
            text, keyboard = _build_item_card(results[idx], idx, len(results))
            await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

    # All decided — show summary + confirm
    summary = _build_summary(session)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Log to Notion", callback_data="confirm"),
            InlineKeyboardButton("🗑️ Cancel", callback_data="cancel"),
        ]
    ])
    await message.reply_text(summary, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# ── Callback handlers ─────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = _sessions.get(user_id)
    data = query.data

    if data == "confirm":
        await _do_confirm(query, session, user_id)
        return

    if data == "cancel":
        _sessions.pop(user_id, None)
        await query.edit_message_text("Cancelled.")
        return

    if not session:
        await query.edit_message_text("Session expired. Send a new photo.")
        return

    action, idx_str = data.split(":", 1)
    idx = int(idx_str)
    result = session["results"][idx]

    if action == "approve":
        if not result["top_matches"]:
            await query.answer("No match to approve — use Search instead.", show_alert=True)
            return
        item = result["top_matches"][0]["item"]
        session["decisions"][idx] = {
            "action": "approved",
            "item_id": item["id"],
            "item_name": item["name"],
        }
        text, _ = _build_item_card(result, idx, len(session["results"]), session["decisions"][idx])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        await _show_next_item(query.message, session, user_id)

    elif action == "alt":
        if len(result["top_matches"]) < 2:
            return
        item = result["top_matches"][1]["item"]
        session["decisions"][idx] = {
            "action": "changed",
            "item_id": item["id"],
            "item_name": item["name"],
        }
        text, _ = _build_item_card(result, idx, len(session["results"]), session["decisions"][idx])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        await _show_next_item(query.message, session, user_id)

    elif action == "skip":
        session["decisions"][idx] = {"action": "skipped", "item_id": None}
        text, _ = _build_item_card(result, idx, len(session["results"]), session["decisions"][idx])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        await _show_next_item(query.message, session, user_id)

    elif action == "search":
        session["searching_for_idx"] = idx
        await query.edit_message_text(
            f"🔍 <b>Search collection</b> for item {idx + 1}:\n"
            f"<i>{_esc(result['identified']['description'][:100])}</i>\n\n"
            "Type any keywords (name, colour, brand, SKU):",
            parse_mode=ParseMode.HTML,
        )


async def handle_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # ── Date text input (when user typed a custom date) ───────────────────────
    pending = _pending.get(user_id)
    if pending and pending.get("waiting_for_date_text"):
        text = update.message.text.strip()
        try:
            date.fromisoformat(text)
        except ValueError:
            await update.message.reply_text("Invalid format. Use YYYY-MM-DD (e.g. 2026-06-15):")
            return
        _pending.pop(user_id, None)
        msg = await update.message.reply_text(
            f"📅 <b>{text}</b>\n\n🔍 Identifying items...", parse_mode=ParseMode.HTML
        )
        await _run_ai_and_review(update, context, pending["all_images"], pending["img_hash"], text,
                                  status_msg=msg)
        return

    session = _sessions.get(user_id)
    if not session or "searching_for_idx" not in session:
        return

    query_text = update.message.text.strip()
    idx = session["searching_for_idx"]

    catalog = collection_cache.load()
    q = query_text.lower()
    matches = [
        item for item in catalog
        if (q in item["name"].lower()
            or q in item["sku"].lower()
            or q in item.get("colour", "").lower()
            or q in item.get("designer", "").lower())
    ][:8]

    if not matches:
        await update.message.reply_text(f"No results for '{_esc(query_text)}'. Try different keywords.")
        return

    buttons = []
    for m in matches:
        label = f"{m['name'][:30]} | {m.get('designer','')[:12]} | {m.get('colour','')[:10]}"
        # Encode name in callback carefully — use item id only, look up name later
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"pick:{idx}:{m['id']}")
        ])
    buttons.append([InlineKeyboardButton("⏭️ Skip this item", callback_data=f"skip:{idx}")])
    await update.message.reply_text(
        f"Results for <b>{_esc(query_text)}</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_setdate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles date selection when EXIF was missing."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    pending = _pending.get(user_id)
    if not pending:
        await query.edit_message_text("Session expired. Send the photo again.")
        return

    chosen = query.data.split(":", 1)[1]  # ISO date or "pick"

    if chosen == "pick":
        _pending[user_id]["waiting_for_date_text"] = True
        await query.edit_message_text(
            "Type the date in format <b>YYYY-MM-DD</b> (e.g. 2026-06-15):",
            parse_mode=ParseMode.HTML,
        )
        return

    _pending.pop(user_id, None)
    await _run_ai_and_review(update, context, pending["all_images"], pending["img_hash"], chosen,
                              status_msg=query.message)


async def handle_always_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split(":", 1)[1]
    catalog = collection_cache.load()
    item = next((c for c in catalog if c["id"] == item_id), None)
    if not item:
        await query.edit_message_text("Item not found in cache. Try /refresh then retry.")
        return
    items = _load_always_worn()
    if any(i["id"] == item_id for i in items):
        await query.edit_message_text(f"{item['name']} is already in your always-worn list.")
        return
    items.append({"id": item_id, "name": item["name"]})
    _save_always_worn(items)
    url = f"https://www.notion.so/{item_id.replace('-', '')}"
    await query.edit_message_text(
        f'💍 Added: <a href="{url}">{_esc(item["name"])}</a>\n\nThis will be included in every OOTD entry.',
        parse_mode=ParseMode.HTML,
    )


async def handle_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = _sessions.get(user_id)
    if not session:
        return

    parts = query.data.split(":", 2)
    idx = int(parts[1])
    item_id = parts[2]

    # Look up item name from cache
    catalog = collection_cache.load()
    item = next((i for i in catalog if i["id"] == item_id), None)
    item_name = item["name"] if item else item_id

    session["decisions"][idx] = {
        "action": "changed",
        "item_id": item_id,
        "item_name": item_name,
    }
    session.pop("searching_for_idx", None)

    await query.edit_message_text(
        f"✏️ Set item {idx + 1} to: <b>{_esc(item_name)}</b>",
        parse_mode=ParseMode.HTML,
    )
    await _show_next_item(query.message, session, user_id)


async def _generate_story_bg(chat_id: int, page_id: str, image_urls: list[str], bot):
    """Generate OOTD story in background and write to Notion page."""
    try:
        msg = await bot.send_message(chat_id, "✍️ Generating OOTD story...")
        loop = asyncio.get_event_loop()
        story = await loop.run_in_executor(
            None, lookbook_mod.generate_story, image_urls[:3]
        )
        if story:
            await loop.run_in_executor(None, lookbook_mod.write_story, page_id, story)
            await msg.edit_text("📖 Story written to Notion.")
        else:
            await msg.edit_text("⚠️ Story generation returned empty.")
    except Exception as e:
        print(f"[story] background generation failed: {e}", file=sys.stderr)


async def _do_confirm(query, session: dict, user_id: int):
    if not session:
        await query.edit_message_text("Session expired.")
        return

    decisions = session["decisions"]
    always = session.get("always_worn_decisions", [])

    always_ids = [d["item_id"] for d in always if d.get("item_id")]
    reviewed_ids = [
        d["item_id"]
        for d in decisions
        if d and d["action"] in ("approved", "changed") and d.get("item_id")
    ]
    seen = set(always_ids)
    item_ids = always_ids + [i for i in reviewed_ids if i not in seen]

    if not item_ids:
        await query.edit_message_text("No items approved. Nothing to log.")
        _sessions.pop(user_id, None)
        return

    # Save decisions to corrections DB so the bot learns
    results = session.get("results", [])
    correction_records = []
    for r, d in zip(results, decisions):
        if d and d["action"] in ("approved", "changed") and d.get("item_id"):
            ident = r["identified"]
            ai_top = r["top_matches"][0]["item"] if r.get("top_matches") else None
            correction_records.append({
                "item_type": ident.get("type", ""),
                "item_colour": ident.get("colour", ""),
                "visual_description": ident.get("description", ""),
                "ai_top_id": ai_top["id"] if ai_top else None,
                "ai_top_name": ai_top["name"] if ai_top else None,
                "correct_id": d["item_id"],
                "correct_name": d["item_name"],
            })
    if correction_records:
        corrections_db.save_decisions(
            session.get("img_hash", ""),
            session["date"],
            correction_records,
        )
        print(f"  [memory] saved {len(correction_records)} decisions to corrections DB", file=sys.stderr)

    all_images = session.get("all_images", [])
    outfit_date = session["date"]
    n_photos = len(all_images)

    await query.edit_message_text(
        f"⏳ Uploading {n_photos} photo{'s' if n_photos > 1 else ''} and creating Notion entry..."
    )

    # Upload each photo to GitHub and collect URLs
    loop = asyncio.get_event_loop()
    image_urls: list[str] = []
    for i, img_bytes in enumerate(all_images):
        suffix = f"_{i+1}" if n_photos > 1 else ""
        url = await loop.run_in_executor(
            None, notion_writer.host_image, img_bytes, outfit_date, suffix
        )
        if url:
            image_urls.append(url)

    try:
        page_id = await loop.run_in_executor(
            None, notion_writer.create_ootd_entry, outfit_date, item_ids,
            image_urls if image_urls else None,
        )
        clean_id = page_id.replace("-", "")
        notion_url = f"https://www.notion.so/{clean_id}"
        img_note = f"📷 {len(image_urls)} photo{'s' if len(image_urls) > 1 else ''} uploaded" if image_urls else "📷 Image: no hosting configured"
        await query.edit_message_text(
            f"✅ <b>Logged!</b>\n\n"
            f"📅 {outfit_date}\n"
            f"👗 {len(item_ids)} item(s) linked\n"
            f"{img_note}\n\n"
            f'<a href="{notion_url}">View in Notion</a>',
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Notion write failed: {e}")
        print(f"Notion write error: {traceback.format_exc()}", file=sys.stderr)
        return

    _sessions.pop(user_id, None)

    # Background story generation (takes 20-30s — don't block the user)
    if image_urls:
        chat_id = query.message.chat_id
        asyncio.create_task(_generate_story_bg(chat_id, page_id, image_urls, query._bot))


# ── Error handler ─────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Unhandled exception:\n{traceback.format_exc()}", file=sys.stderr)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"⚠️ Something went wrong:\n<code>{_esc(str(context.error))}</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    request = HTTPXRequest(read_timeout=60, connect_timeout=20, write_timeout=60, media_write_timeout=60)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("date", cmd_date))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("always", cmd_always))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(handle_setdate_callback, pattern=r"^setdate:"))
    app.add_handler(CallbackQueryHandler(handle_always_add_callback, pattern=r"^always_add:"))
    app.add_handler(CallbackQueryHandler(handle_pick_callback, pattern=r"^pick:"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text))

    app.add_error_handler(error_handler)

    print("WIS Outfit Bot starting...", flush=True)
    app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
