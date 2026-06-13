from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.requests import (
    create_rss_feed, get_chat_rss_feeds, remove_rss_feed,
)
from bot.filters.admin import IsAdminFilter
from bot.filters.chat_type import IsGroupFilter

router = Router()


@router.message(Command("addfeed"), IsGroupFilter())
async def cmd_addfeed(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "❌ Использование: /addfeed <code>URL</code> [интервал_в_мин]\n"
            "Пример: /addfeed https://example.com/rss 30"
        )
        return

    url = parts[1]
    interval = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 15

    if not url.startswith("http"):
        await message.answer("❌ URL должен начинаться с http:// или https://")
        return

    existing = await get_chat_rss_feeds(message.chat.id)
    if len(existing) >= 10:
        await message.answer("❌ Максимум 10 RSS-подписок на чат.")
        return

    feed = await create_rss_feed(
        chat_id=message.chat.id, url=url,
        interval_minutes=interval, created_by=message.from_user.id,
    )
    await message.answer(
        f"✅ RSS-лента добавлена!\n"
        f"🆔 ID: <code>{feed.id}</code>\n"
        f"📡 URL: {url}\n"
        f"🕐 Интервал: {interval} мин."
    )


@router.message(Command("feeds"), IsGroupFilter())
async def cmd_feeds(message: Message):
    feeds = await get_chat_rss_feeds(message.chat.id)
    if not feeds:
        await message.answer("📭 Нет активных RSS-подписок.\n/addfeed <code>URL</code> — добавить")
        return

    lines = [f"<b>📡 RSS-подписки в {message.chat.title}:</b>\n"]
    for f in feeds:
        title = f.title or f.url[:40]
        lines.append(f"• <code>#{f.id}</code> {title} | каждые {f.interval_minutes} мин.")
    lines.append("\n/removefeed <code>ID</code> — удалить")

    await message.answer("\n".join(lines))


@router.message(Command("removefeed"), IsGroupFilter())
async def cmd_removefeed(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Использование: /removefeed <code>ID</code>")
        return
    removed = await remove_rss_feed(int(args[1]))
    await message.answer("✅ RSS-лента удалена" if removed else "❌ Не найдена")
