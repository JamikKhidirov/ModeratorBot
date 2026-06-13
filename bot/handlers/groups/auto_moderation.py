import re
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import Message, ChatPermissions
from sqlalchemy import select

from bot.database.base import get_session
from bot.database.requests import (
    get_chat_settings, get_word_triggers, increment_message_count, add_warning, add_punishment,
)
from bot.database.models import Chat, TriggerAction, PunishmentType
from bot.filters.chat_type import IsGroupFilter

router = Router()
router.message.filter(IsGroupFilter())

URL_PATTERN = re.compile(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*", re.IGNORECASE)


async def is_admin_or_mod(bot, chat_id, user_id) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


@router.message(F.text | F.photo | F.video | F.sticker | F.animation | F.document)
async def auto_moderate(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if message.from_user.is_bot:
        return

    if await is_admin_or_mod(message.bot, chat_id, user_id):
        return

    await increment_message_count(user_id, chat_id)

    settings = await get_chat_settings(chat_id)
    chat = await get_chat_model(chat_id)

    if not settings:
        return

    text = message.text or message.caption or ""

    # ─── Sticker filter ──────────────────────────────────────
    if chat and chat.delete_stickers and message.sticker:
        try:
            await message.delete()
        except Exception:
            pass
        return

    # ─── Media filter ────────────────────────────────────────
    if chat and chat.delete_media and (message.photo or message.video or message.animation or message.document):
        try:
            await message.delete()
        except Exception:
            pass
        return

    if not text:
        return

    # ─── Link filter ─────────────────────────────────────────
    if settings.delete_links and URL_PATTERN.search(text):
        try:
            await message.delete()
            if settings.auto_mute_links:
                duration = settings.mute_duration or 60
                await message.chat.restrict(
                    user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=timedelta(seconds=duration),
                )
        except Exception:
            pass
        return

    # ─── Bad words filter ───────────────────────────────────
    if settings.delete_bad_words and settings.bad_words:
        bad_words_list = [w.strip().lower() for w in settings.bad_words.split(",") if w.strip()]
        text_lower = text.lower()
        for word in bad_words_list:
            if word in text_lower:
                try:
                    await message.delete()
                except Exception:
                    pass
                return

    # ─── Word triggers ──────────────────────────────────────
    triggers = await get_word_triggers(chat_id)
    if triggers:
        text_lower = text.lower()
        for trigger in triggers:
            trigger_word = trigger.word.lower()
            if (trigger.case_sensitive and trigger.word in text) or \
               (not trigger.case_sensitive and trigger_word in text_lower):

                action = trigger.action
                try:
                    if action in (TriggerAction.DELETE, TriggerAction.DELETE_WARN, TriggerAction.DELETE_MUTE):
                        await message.delete()

                    if action in (TriggerAction.WARN, TriggerAction.DELETE_WARN):
                        await add_warning(user_id, chat_id, message.bot.id, reason=f"Триггер: {trigger.word}")
                        settings_model = await get_chat_settings(chat_id)
                        max_warns = settings_model.max_warns if settings_model else 3
                        warn_count = await count_warnings_db(user_id, chat_id)
                        if warn_count >= max_warns:
                            try:
                                await message.chat.ban(user_id)
                            except Exception:
                                pass

                    if action in (TriggerAction.MUTE, TriggerAction.DELETE_MUTE):
                        duration = trigger.mute_duration or 300
                        await message.chat.restrict(
                            user_id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=timedelta(seconds=duration),
                        )
                        await add_punishment(user_id, chat_id, message.bot.id, PunishmentType.MUTE, duration=duration)

                    if action == TriggerAction.BAN:
                        await add_punishment(user_id, chat_id, message.bot.id, PunishmentType.BAN)
                        try:
                            await message.chat.ban(user_id)
                        except Exception:
                            pass
                except Exception:
                    pass
                return


async def get_chat_model(chat_id: int):
    async with get_session() as session:
        result = await session.execute(select(Chat).where(Chat.id == chat_id))
        return result.scalar_one_or_none()


async def count_warnings_db(user_id: int, chat_id: int) -> int:
    from sqlalchemy import func, and_
    from bot.database.models import Warning
    from bot.database.base import get_session
    async with get_session() as session:
        r = await session.execute(
            select(func.count(Warning.id)).where(
                and_(Warning.user_id == user_id, Warning.chat_id == chat_id)
            )
        )
        return r.scalar() or 0
