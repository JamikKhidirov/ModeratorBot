from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.requests import (
    get_message_stats, get_top_users, get_user, get_warnings_count,
)
from bot.database.base import get_session
from bot.database.models import MessageCount
from bot.filters.chat_type import IsGroupFilter
from sqlalchemy import select, func

router = Router()


@router.message(Command("stat"), IsGroupFilter())
async def cmd_stat(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    count = await get_message_stats(target.id, message.chat.id)
    warns = await get_warnings_count(target.id, message.chat.id)

    await message.answer(
        f"📊 <b>Статистика для {target.full_name}</b>\n\n"
        f"💬 Сообщений: <code>{count}</code>\n"
        f"⚠️ Варнов: <code>{warns}</code>"
    )


@router.message(Command("top"), IsGroupFilter())
async def cmd_top(message: Message):
    top = await get_top_users(message.chat.id, 10)
    if not top:
        await message.answer("📭 В этом чате пока нет статистики сообщений.")
        return

    lines = [f"<b>🏆 Топ-10 активных пользователей в {message.chat.title}</b>\n"]
    for i, mc in enumerate(top, 1):
        user = await get_user(mc.user_id)
        name = user.first_name if user else f"ID {mc.user_id}"
        lines.append(f"{i}. {name} — <code>{mc.count}</code> сообщений")

    await message.answer("\n".join(lines))


@router.message(Command("mystat"))
async def cmd_mystat(message: Message):
    counts = await get_message_stats(message.from_user.id)
    if not counts:
        await message.answer("📭 У вас пока нет статистики сообщений.")
        return

    total = sum(c.count for c in counts)
    chats = len(counts)
    await message.answer(
        f"📊 <b>Ваша общая статистика</b>\n\n"
        f"💬 Всего сообщений: <code>{total}</code>\n"
        f"💬 В чатах: <code>{chats}</code>"
    )
