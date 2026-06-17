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

import os, sys, base64, asyncio, traceback
from io import BytesIO
from datetime import date
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
from PIL import Image
from PIL.ExifTags import TAGS
from dotenv import load_dotenv

load_dotenv()

import collection_cache
import vision_matcher
import notion_writer

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

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

    lines = [f"<b>Item {idx + 1} of {total}</b> {emoji}"]
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
    approved = [(r, d) for r, d in zip(results, decisions) if d and d["action"] in ("approved", "changed")]
    skipped = [r for r, d in zip(results, decisions) if d and d["action"] == "skipped"]

    lines = ["<b>Review Summary</b>\n"]
    for r, d in approved:
        item_name = d.get("item_name") or r["top_matches"][0]["item"]["name"]
        item_id = d.get("item_id", "")
        if item_id:
            # Find item in results to get full item dict for URL
            url = f"https://www.notion.so/{item_id.replace('-', '')}"
            lines.append(f'✅ <a href="{url}">{_esc(item_name)}</a>')
        else:
            lines.append(f"✅ {_esc(item_name)}")
    for r in skipped:
        lines.append(f"⏭️ <i>{_esc(r['identified']['type'])} — skipped</i>")

    lines.append(f"\n<b>Date:</b> {session['date']}")
    lines.append(f"<b>Items to link:</b> {len(approved)}")
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


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Refreshing collection cache...")
    try:
        items = collection_cache.refresh()
        await msg.edit_text(f"Cache refreshed. {len(items)} items loaded.")
    except Exception as e:
        await msg.edit_text(f"Refresh failed: {e}")


# ── Photo handler ─────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("📸 Received. Downloading...")

    # Get highest-res version
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    buf = BytesIO()
    await file.download_to_memory(buf)
    raw_bytes = buf.getvalue()

    image_bytes = _resize_for_vision(raw_bytes)
    image_b64 = base64.standard_b64encode(image_bytes).decode()

    # Determine date
    if user_id in _date_override:
        outfit_date = _date_override.pop(user_id)
        date_source = "override"
    else:
        exif_date = _extract_exif_date(raw_bytes)
        outfit_date = exif_date or date.today().isoformat()
        date_source = "EXIF" if exif_date else "today"

    await msg.edit_text(
        f"📅 <b>{outfit_date}</b> (from {date_source})\n\n🔍 Identifying items...",
        parse_mode=ParseMode.HTML,
    )

    try:
        catalog = collection_cache.load()
    except Exception as e:
        await msg.edit_text(f"Failed to load collection: {e}")
        return

    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None, vision_matcher.run_matching, image_b64, catalog
        )
    except Exception as e:
        await msg.edit_text(f"AI matching failed: {e}")
        print(f"run_matching error: {traceback.format_exc()}", file=sys.stderr)
        return

    if not results:
        await msg.edit_text("Could not identify any items. Try a clearer photo.")
        return

    _sessions[user_id] = {
        "image_bytes": raw_bytes,
        "date": outfit_date,
        "results": results,
        "decisions": [None] * len(results),
    }

    matched = sum(1 for r in results if r["status"] == "matched")
    ambiguous = sum(1 for r in results if r["status"] == "ambiguous")
    unidentified = sum(1 for r in results if r["status"] == "unidentified")

    await msg.edit_text(
        f"Found <b>{len(results)} item(s)</b> — "
        f"{matched} matched, {ambiguous} ambiguous, {unidentified} unidentified.\n"
        f"Reviewing one by one:",
        parse_mode=ParseMode.HTML,
    )
    await _show_next_item(update.message, _sessions[user_id], user_id)


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


async def _do_confirm(query, session: dict, user_id: int):
    if not session:
        await query.edit_message_text("Session expired.")
        return

    decisions = session["decisions"]
    item_ids = [
        d["item_id"]
        for d in decisions
        if d and d["action"] in ("approved", "changed") and d.get("item_id")
    ]

    if not item_ids:
        await query.edit_message_text("No items approved. Nothing to log.")
        _sessions.pop(user_id, None)
        return

    await query.edit_message_text("⏳ Uploading image and creating Notion entry...")

    image_url = await asyncio.get_event_loop().run_in_executor(
        None, notion_writer.host_image, session["image_bytes"], session["date"], "",
    )

    try:
        page_id = await asyncio.get_event_loop().run_in_executor(
            None, notion_writer.create_ootd_entry, session["date"], item_ids, image_url,
        )
        clean_id = page_id.replace("-", "")
        notion_url = f"https://www.notion.so/{clean_id}"
        img_note = "📷 Image uploaded" if image_url else "📷 Image: no hosting configured"
        await query.edit_message_text(
            f"✅ <b>Logged!</b>\n\n"
            f"📅 {session['date']}\n"
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
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("date", cmd_date))
    app.add_handler(CommandHandler("refresh", cmd_refresh))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_pick_callback, pattern=r"^pick:"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text))

    app.add_error_handler(error_handler)

    print("WIS Outfit Bot starting...", flush=True)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
