#!/usr/bin/env python3
"""
WIS Outfit Bot — Telegram bot for OOTD outfit logging.

Send a mirror selfie → AI identifies items → review queue → Notion entry created.

Usage:
    python3 outfit_bot.py

Commands:
    /start       — welcome
    /review      — re-show pending review queue (if any)
    /date YYYY-MM-DD — override date for next outfit
    /refresh     — force-refresh collection cache
    /help        — command list
"""

import os, sys, base64, asyncio, json
from io import BytesIO
from datetime import date
from pathlib import Path

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
# Keyed by user_id. Each session:
# {
#   "image_bytes": bytes,
#   "image_b64": str,
#   "date": str (YYYY-MM-DD),
#   "results": list[dict],   # from vision_matcher.run_matching
#   "decisions": list,       # parallel to results; each: {"action": "approved"|"skipped", "item_id": str|None}
#   "current_idx": int,      # which result we're reviewing
# }
_sessions: dict[int, dict] = {}
_date_override: dict[int, str] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _build_item_card(result: dict, idx: int, total: int, decision: dict | None = None) -> tuple[str, InlineKeyboardMarkup]:
    ident = result["identified"]
    status = result["status"]
    emoji = _status_emoji(status)

    lines = [f"*Item {idx + 1} of {total}* {emoji}"]
    lines.append(f"_{ident['type'].title()} — {ident['colour']}_")
    lines.append(f"> {ident['description'][:120]}")
    lines.append("")

    top = result["top_matches"]
    if top:
        best = top[0]
        item = best["item"]
        conf_pct = int(best["confidence"] * 100)
        lines.append(f"*Best match ({conf_pct}%):*")
        designer = item.get("designer", "")
        colour = item.get("colour", "")
        lines.append(f"`{item['name']}`")
        if designer:
            lines.append(f"  {designer}")
        if colour:
            lines.append(f"  {colour}")
        lines.append(f"  SKU: `{item['sku']}`")
        if len(top) > 1:
            alt = top[1]
            alt_item = alt["item"]
            lines.append(f"\n_Alt ({int(alt['confidence']*100)}%): {alt_item['name']}_")
    else:
        lines.append("_No match found in collection_")

    if decision:
        action = decision["action"]
        if action == "approved":
            lines.append(f"\n✅ *Approved*")
        elif action == "skipped":
            lines.append(f"\n⏭️ *Skipped*")
        elif action == "changed":
            lines.append(f"\n✏️ *Changed to:* {decision.get('item_name', '?')}")

    text = "\n".join(lines)

    buttons = []
    if not decision:
        row1 = [
            InlineKeyboardButton("✅ Correct", callback_data=f"approve:{idx}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{idx}"),
        ]
        row2 = [InlineKeyboardButton("🔍 Search collection", callback_data=f"search:{idx}")]
        buttons = [row1, row2]
        if len(top) > 1:
            alt_item = top[1]["item"]
            buttons.insert(1, [
                InlineKeyboardButton(
                    f"↕️ Use alt: {alt_item['name'][:25]}",
                    callback_data=f"alt:{idx}",
                )
            ])

    return text, InlineKeyboardMarkup(buttons) if buttons else InlineKeyboardMarkup([])


def _build_summary(session: dict) -> str:
    results = session["results"]
    decisions = session["decisions"]
    approved = [(r, d) for r, d in zip(results, decisions) if d and d["action"] in ("approved", "changed")]
    skipped = [r for r, d in zip(results, decisions) if d and d["action"] == "skipped"]
    undecided = [r for r, d in zip(results, decisions) if not d]

    lines = ["*Review Summary*\n"]
    for r, d in approved:
        item_name = d.get("item_name") or r["top_matches"][0]["item"]["name"]
        lines.append(f"✅ {item_name}")
    for r in skipped:
        lines.append(f"⏭️ _{r['identified']['type']} — skipped_")
    for r in undecided:
        lines.append(f"⬜ _{r['identified']['type']} — not reviewed_")

    lines.append(f"\n*Date:* {session['date']}")
    lines.append(f"*Items to link:* {len(approved)}")
    return "\n".join(lines)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*WIS Outfit Bot*\n\n"
        "Send me a mirror selfie and I'll identify what you're wearing, "
        "match items to your collection, and log the outfit to Notion.\n\n"
        "Commands:\n"
        "/date YYYY-MM-DD — override date for next outfit\n"
        "/refresh — reload collection cache\n"
        "/help — this message",
        parse_mode=ParseMode.MARKDOWN,
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
        await update.message.reply_text(f"Date override set: *{date_str}*\nSend your outfit photo.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("Invalid date. Use format: YYYY-MM-DD (e.g. /date 2026-06-15)")


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Refreshing collection cache...")
    try:
        items = collection_cache.refresh()
        await msg.edit_text(f"Cache refreshed. {len(items)} items loaded.")
    except Exception as e:
        await msg.edit_text(f"Refresh failed: {e}")


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = _sessions.get(user_id)
    if not session:
        await update.message.reply_text("No active review session. Send a photo to start.")
        return
    await _show_next_item(update.message, session, user_id)


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

    # Resize for vision (keep token cost manageable)
    image_bytes = _resize_for_vision(raw_bytes)
    image_b64 = base64.standard_b64encode(image_bytes).decode()

    # Determine date
    if user_id in _date_override:
        outfit_date = _date_override.pop(user_id)
        date_source = "override"
    else:
        outfit_date = _extract_exif_date(raw_bytes) or date.today().isoformat()
        date_source = "EXIF" if _extract_exif_date(raw_bytes) else "today"

    await msg.edit_text(f"📅 Date: *{outfit_date}* (from {date_source})\n\n🔍 Identifying items...", parse_mode=ParseMode.MARKDOWN)

    # Load catalog
    try:
        catalog = collection_cache.load()
    except Exception as e:
        await msg.edit_text(f"Failed to load collection: {e}")
        return

    # Run AI matching
    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None, vision_matcher.run_matching, image_b64, catalog
        )
    except Exception as e:
        await msg.edit_text(f"AI matching failed: {e}")
        return

    if not results:
        await msg.edit_text("Could not identify any items. Try a clearer photo.")
        return

    # Build session
    _sessions[user_id] = {
        "image_bytes": raw_bytes,
        "image_b64": image_b64,
        "date": outfit_date,
        "results": results,
        "decisions": [None] * len(results),
        "current_idx": 0,
    }

    await msg.edit_text(
        f"Found *{len(results)} item(s)*. Let's review them one by one.",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _show_next_item(update.message, _sessions[user_id], user_id)


async def _show_next_item(message, session: dict, user_id: int):
    """Show the next undecided item card, or the confirm prompt if done."""
    results = session["results"]
    decisions = session["decisions"]

    # Find next undecided
    for idx in range(len(results)):
        if decisions[idx] is None:
            session["current_idx"] = idx
            text, keyboard = _build_item_card(results[idx], idx, len(results))
            await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            return

    # All decided — show summary and confirm button
    summary = _build_summary(session)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Log to Notion", callback_data="confirm"),
            InlineKeyboardButton("🗑️ Cancel", callback_data="cancel"),
        ]
    ])
    await message.reply_text(summary, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


# ── Callback query handlers ───────────────────────────────────────────────────

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
        await query.edit_message_text("Cancelled. Session cleared.")
        return

    if not session:
        await query.edit_message_text("Session expired. Send a new photo.")
        return

    action, idx_str = data.split(":", 1)
    idx = int(idx_str)
    result = session["results"][idx]

    if action == "approve":
        item = result["top_matches"][0]["item"]
        session["decisions"][idx] = {
            "action": "approved",
            "item_id": item["id"],
            "item_name": item["name"],
        }
        text, _ = _build_item_card(result, idx, len(session["results"]), session["decisions"][idx])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([]))
        await _show_next_item(query.message, session, user_id)

    elif action == "alt":
        # Use the second match instead
        if len(result["top_matches"]) > 1:
            item = result["top_matches"][1]["item"]
            session["decisions"][idx] = {
                "action": "changed",
                "item_id": item["id"],
                "item_name": item["name"],
            }
            text, _ = _build_item_card(result, idx, len(session["results"]), session["decisions"][idx])
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([]))
            await _show_next_item(query.message, session, user_id)

    elif action == "skip":
        session["decisions"][idx] = {"action": "skipped", "item_id": None}
        text, _ = _build_item_card(result, idx, len(session["results"]), session["decisions"][idx])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([]))
        await _show_next_item(query.message, session, user_id)

    elif action == "search":
        # Enter search mode — next text message from user will be treated as a search query
        session["searching_for_idx"] = idx
        await query.edit_message_text(
            f"🔍 Search your collection for item {idx + 1}:\n"
            f"_{result['identified']['description'][:100]}_\n\n"
            "Type any keywords (name, colour, brand, SKU):",
            parse_mode=ParseMode.MARKDOWN,
        )


async def handle_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text during search mode."""
    user_id = update.effective_user.id
    session = _sessions.get(user_id)
    if not session or "searching_for_idx" not in session:
        return  # not in search mode — ignore

    query_text = update.message.text.strip()
    idx = session["searching_for_idx"]
    result = session["results"][idx]

    catalog = collection_cache.load()
    # Simple keyword search across name, sku, colour, designer
    q = query_text.lower()
    matches = [
        item for item in catalog
        if (q in item["name"].lower()
            or q in item["sku"].lower()
            or q in item.get("colour", "").lower()
            or q in item.get("designer", "").lower())
    ][:8]

    if not matches:
        await update.message.reply_text(f"No results for '{query_text}'. Try different keywords:")
        return

    buttons = [
        [InlineKeyboardButton(
            f"{m['name'][:30]} | {m.get('designer','')[:12]} | {m.get('colour','')[:10]}",
            callback_data=f"pick:{idx}:{m['id']}:{m['name'][:20]}",
        )]
        for m in matches
    ]
    buttons.append([InlineKeyboardButton("⏭️ Skip this item", callback_data=f"skip:{idx}")])
    await update.message.reply_text(
        f"Results for '{query_text}':",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle item selection from search results."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = _sessions.get(user_id)
    if not session:
        return

    parts = query.data.split(":", 3)
    # "pick:{idx}:{item_id}:{item_name}"
    idx = int(parts[1])
    item_id = parts[2]
    item_name = parts[3] if len(parts) > 3 else "?"

    session["decisions"][idx] = {
        "action": "changed",
        "item_id": item_id,
        "item_name": item_name,
    }
    session.pop("searching_for_idx", None)

    await query.edit_message_text(
        f"✏️ Set item {idx + 1} to: *{item_name}*",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _show_next_item(query.message, session, user_id)


async def _do_confirm(query, session: dict, user_id: int):
    """Create Notion OOTD entry with approved items."""
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

    # Upload image
    image_url = await asyncio.get_event_loop().run_in_executor(
        None,
        notion_writer.host_image,
        session["image_bytes"],
        session["date"],
        "",
    )

    # Create Notion entry
    try:
        page_id = await asyncio.get_event_loop().run_in_executor(
            None,
            notion_writer.create_ootd_entry,
            session["date"],
            item_ids,
            image_url,
        )
        clean_id = page_id.replace("-", "")
        notion_url = f"https://www.notion.so/{clean_id}"
        img_note = f"\n📷 Image: uploaded" if image_url else "\n📷 Image: not uploaded (no hosting configured)"
        await query.edit_message_text(
            f"✅ *Logged!*\n\n"
            f"📅 {session['date']}\n"
            f"👗 {len(item_ids)} item(s) linked\n"
            f"{img_note}\n\n"
            f"[View in Notion]({notion_url})",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Notion write failed: {e}")
        return

    _sessions.pop(user_id, None)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("date", cmd_date))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("review", cmd_review))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Callback routing
    app.add_handler(CallbackQueryHandler(handle_pick_callback, pattern=r"^pick:"))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text messages during search mode
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text))

    print("WIS Outfit Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
