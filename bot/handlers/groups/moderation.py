from datetime import timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatPermissions

from bot.database.requests import (
    add_warning, clear_warnings, get_warnings_count, get_chat_settings,
    add_punishment, deactivate_punishment, get_user, is_chat_admin_assigned,
    update_chat_settings, get_word_triggers, add_word_trigger, remove_word_trigger,
)
from bot.database.models import PunishmentType, UserRole, TriggerAction
from bot.filters.chat_type import IsGroupFilter
from bot.utils.logger import log_action
from bot.utils.helpers import format_duration, parse_duration, mention_user
from bot.utils.texts import (
    MUTE_SUCCESS, UNMUTE_SUCCESS, BAN_SUCCESS, UNBAN_SUCCESS,
    KICK_SUCCESS, WARN_SUCCESS, WARN_BAN, CLEAR_SUCCESS,
    NO_RIGHTS, NOWARN_TEXT,
)
from bot.keyboards.inline import back_kb

router = Router()
router.message.filter(IsGroupFilter())


async def check_bot_admin(message: Message) -> bool:
    try:
        bot_member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
        return bot_member.status in ("administrator", "creator")
    except Exception:
        return False


async def check_user_can_moderate(message: Message) -> bool:
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = await get_user(user_id)
    if user and user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        return True
    if await is_chat_admin_assigned(user_id, chat_id):
        return True
    from bot.database.requests import is_group_moderator
    if await is_group_moderator(user_id, chat_id):
        return True
    try:
        member = await message.chat.get_member(user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def get_target(message: Message):
    if message.reply_to_message:
        return message.reply_to_message.from_user
    args = message.text.split()
    return None


@router.message(Command("mute"))
async def cmd_mute(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    target = get_target(message)
    if not target:
        return await message.answer(
            "❌ Использование: <code>/mute [время] [причина]</code>\n"
            "Ответьте на сообщение пользователя.\n"
            "Пример: <code>/mute 30м Спам</code>"
        )
    if target.id == message.bot.id:
        return await message.answer("❌ Нельзя замутить бота.")

    args = message.text.split(maxsplit=1)
    duration = 3600
    reason = None
    if len(args) > 1:
        parts = args[1].split(maxsplit=1)
        parsed = parse_duration(parts[0])
        if parsed:
            duration = parsed
            if len(parts) > 1:
                reason = parts[1]
        else:
            reason = args[1]

    try:
        await add_punishment(
            user_id=target.id, chat_id=message.chat.id,
            moderator_id=message.from_user.id,
            ptype=PunishmentType.MUTE, duration=duration, reason=reason,
        )
        permissions = ChatPermissions(
            can_send_messages=False, can_send_media_messages=False,
            can_send_other_messages=False, can_add_web_page_previews=False,
        )
        await message.chat.restrict(user_id=target.id, permissions=permissions, until_date=timedelta(seconds=duration))
        name = target.full_name or str(target.id)
        await message.answer(MUTE_SUCCESS.format(user_id=target.id, name=name, duration=format_duration(duration)))
        await log_action(message.chat.id, "MUTE", message.from_user.full_name, target.full_name, reason=reason, duration=format_duration(duration))
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    target = get_target(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы размутить.")

    try:
        await deactivate_punishment(target.id, message.chat.id, PunishmentType.MUTE)
        permissions = ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True,
            can_send_polls=True, can_change_info=False,
            can_invite_users=True, can_pin_messages=False,
        )
        await message.chat.restrict(user_id=target.id, permissions=permissions)
        name = target.full_name or str(target.id)
        await message.answer(UNMUTE_SUCCESS.format(user_id=target.id, name=name))
        await log_action(message.chat.id, "UNMUTE", message.from_user.full_name, target.full_name)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    target = get_target(message)
    if not target:
        return await message.answer(
            "❌ Использование: <code>/ban [причина]</code>\n"
            "Ответьте на сообщение пользователя."
        )
    if target.id == message.bot.id:
        return await message.answer("❌ Нельзя забанить бота.")

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else None

    try:
        await add_punishment(user_id=target.id, chat_id=message.chat.id, moderator_id=message.from_user.id, ptype=PunishmentType.BAN, reason=reason)
        await message.chat.ban(user_id=target.id)
        name = target.full_name or str(target.id)
        await message.answer(BAN_SUCCESS.format(user_id=target.id, name=name))
        await log_action(message.chat.id, "BAN", message.from_user.full_name, target.full_name, reason=reason)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    target = get_target(message)
    if not target:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.answer("❌ Использование: <code>/unban @username</code> или ответьте на сообщение.")
        try:
            user_id = int(args[1].lstrip("@"))
            await deactivate_punishment(user_id, message.chat.id, PunishmentType.BAN)
            await message.chat.unban(user_id=user_id)
            await message.answer(UNBAN_SUCCESS.format(user_id=user_id, name=args[1]))
            return
        except (ValueError, Exception) as e:
            return await message.answer(f"❌ Ошибка: {e}")

    try:
        await deactivate_punishment(target.id, message.chat.id, PunishmentType.BAN)
        await message.chat.unban(user_id=target.id)
        name = target.full_name or str(target.id)
        await message.answer(UNBAN_SUCCESS.format(user_id=target.id, name=name))
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("kick"))
async def cmd_kick(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    target = get_target(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы кикнуть.")
    if target.id == message.bot.id:
        return await message.answer("❌ Нельзя кикнуть бота.")

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else None

    try:
        await add_punishment(user_id=target.id, chat_id=message.chat.id, moderator_id=message.from_user.id, ptype=PunishmentType.KICK, reason=reason)
        await message.chat.ban(user_id=target.id)
        await message.chat.unban(user_id=target.id)
        name = target.full_name or str(target.id)
        await message.answer(KICK_SUCCESS.format(user_id=target.id, name=name))
        await log_action(message.chat.id, "KICK", message.from_user.full_name, target.full_name, reason=reason)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("warn"))
async def cmd_warn(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    target = get_target(message)
    if not target:
        return await message.answer(
            "❌ Использование: <code>/warn [причина]</code>\n"
            "Ответьте на сообщение пользователя."
        )

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else None

    settings = await get_chat_settings(message.chat.id)
    max_warns = settings.max_warns if settings else 3
    warn_count = await add_warning(user_id=target.id, chat_id=message.chat.id, moderator_id=message.from_user.id, reason=reason)

    name = target.full_name or str(target.id)
    if warn_count >= max_warns:
        try:
            await message.chat.ban(user_id=target.id)
        except Exception as e:
            return await message.answer(f"❌ Ошибка при бане: {e}")
        await clear_warnings(target.id, message.chat.id)
        await message.answer(WARN_BAN.format(user_id=target.id, name=name))
    else:
        await message.answer(WARN_SUCCESS.format(user_id=target.id, name=name, count=warn_count, max=max_warns, reason=reason or "Без причины"))
        await log_action(message.chat.id, "WARN", message.from_user.full_name, target.full_name, reason=reason)


@router.message(Command("clear"))
async def cmd_clear(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    args = message.text.split()
    count = 10
    if len(args) > 1 and args[1].isdigit():
        count = min(int(args[1]), 100)

    if message.reply_to_message:
        try:
            msg_ids = [message.reply_to_message.message_id]
            msg_ids.append(message.message_id)
            await message.bot.delete_messages(message.chat.id, msg_ids)
            await message.answer(CLEAR_SUCCESS.format(count=len(msg_ids)))
        except Exception:
            await message.answer("❌ Не удалось удалить сообщения (возможно, они старше 48 часов).")
    else:
        await message.delete()
        await message.answer(CLEAR_SUCCESS.format(count=1))


@router.message(Command("warns"))
async def cmd_warns(message: Message):
    target = get_target(message) or message.from_user
    count = await get_warnings_count(target.id, message.chat.id)
    if count == 0:
        return await message.answer(f"✅ У {target.full_name} нет варнов.")
    await message.answer(f"⚠️ Варнов у {target.full_name}: {count}")


@router.message(Command("warnlist"))
async def cmd_warnlist(message: Message):
    target = get_target(message) or message.from_user
    from bot.database.base import get_session
    from bot.database.models import Warning as WarnModel
    from sqlalchemy import select
    async with get_session() as session:
        result = await session.execute(
            select(WarnModel).where(WarnModel.user_id == target.id, WarnModel.chat_id == message.chat.id)
            .order_by(WarnModel.created_at.desc())
        )
        warns = list(result.scalars().all())
    if not warns:
        return await message.answer(f"✅ У {target.full_name} нет варнов.")
    lines = [f"<b>⚠️ Варны {target.full_name}:</b>\n"]
    for w in warns:
        lines.append(f"• {w.created_at.strftime('%d.%m %H:%M')} — {w.reason or 'Без причины'}")
    await message.answer("\n".join(lines))


@router.message(Command("clearwarns"))
async def cmd_clearwarns(message: Message):
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    target = get_target(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы очистить варны.")
    await clear_warnings(target.id, message.chat.id)
    await message.answer(f"✅ Варны {target.full_name} очищены.")


@router.message(Command("del"))
async def cmd_del(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав модератора.")
    if not message.reply_to_message:
        return await message.answer("❌ Ответьте на сообщение для удаления.")
    try:
        await message.reply_to_message.delete()
        await message.delete()
    except Exception:
        await message.answer("❌ Не удалось удалить (возможно, сообщение старше 48 часов).")


@router.message(Command("lock"))
async def cmd_lock(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    try:
        await message.chat.set_permissions(ChatPermissions(can_send_messages=False))
        await message.answer("🔒 Чат заблокирован. Только админы могут писать.")
        await log_action(message.chat.id, "LOCK", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав для блокировки чата.")


@router.message(Command("unlock"))
async def cmd_unlock(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    try:
        await message.chat.set_permissions(
            ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True, can_send_polls=True, can_invite_users=True)
        )
        await message.answer("🔓 Чат разблокирован.")
        await log_action(message.chat.id, "UNLOCK", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав для разблокировки чата.")


@router.message(Command("slowmode"))
async def cmd_slowmode(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    seconds = 10
    if len(args) > 1:
        parsed = parse_duration(args[1])
        if parsed:
            seconds = min(parsed, 3600)
        elif args[1].isdigit():
            seconds = min(int(args[1]), 3600)
    try:
        await message.chat.set_slow_mode_delay(seconds)
        await message.answer(f"🐢 Slowmode установлен: {seconds} сек.")
    except Exception:
        await message.answer("❌ Нет прав для установки slowmode.")


@router.message(Command("banlist"))
async def cmd_banlist(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    await message.answer(f"<b>🚫 Забаненные в {message.chat.title}:</b>\n\nTelegram API не предоставляет список забаненных.")


@router.message(Command("kickme"))
async def cmd_kickme(message: Message):
    try:
        await message.chat.ban(message.from_user.id)
        await message.chat.unban(message.from_user.id)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("admins"))
async def cmd_admins(message: Message):
    try:
        admins = []
        async for m in message.bot.get_chat_administrators(message.chat.id):
            user = m.user
            title = m.custom_title or ""
            admins.append(f"• {user.full_name} (@{user.username or '—'}) {title}")
        lines = [f"<b>👑 Админы {message.chat.title}:</b>\n"] + admins
        await message.answer("\n".join(lines))
    except Exception:
        await message.answer("❌ Нет доступа.")


@router.message(Command("settitle"))
async def cmd_settitle(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Использование: <code>/settitle Новый заголовок</code>")
    try:
        await message.chat.set_title(args[1])
        await message.answer(f"✅ Название чата изменено на «{args[1]}».")
    except Exception:
        await message.answer("❌ Нет прав для изменения названия.")


@router.message(Command("setdescription"))
async def cmd_setdescription(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Использование: <code>/setdescription Текст</code>")
    try:
        await message.chat.set_description(args[1])
        await message.answer(f"✅ Описание чата изменено.")
    except Exception:
        await message.answer("❌ Нет прав для изменения описания.")


@router.message(Command("leave"))
async def cmd_leave(message: Message):
    if not await check_user_can_moderate(message):
        return await message.answer("❌ Только администратор может удалить бота.")
    await message.answer("👋 Пока!")
    await message.chat.leave()


@router.message(Command("mute_all"))
async def cmd_mute_all(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    try:
        await message.chat.set_permissions(ChatPermissions(can_send_messages=False))
        await message.answer("🔇 Все участники замучены.")
        await log_action(message.chat.id, "MUTE_ALL", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав для mute_all.")


@router.message(Command("unmute_all"))
async def cmd_unmute_all(message: Message):
    if not await check_bot_admin(message):
        return await message.answer(NO_RIGHTS)
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    try:
        await message.chat.set_permissions(
            ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True, can_send_polls=True, can_invite_users=True)
        )
        await message.answer("🔊 Все участники размучены.")
        await log_action(message.chat.id, "UNMUTE_ALL", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав для unmute_all.")


# ─── Word Ban Commands ──────────────────────────────────────

@router.message(Command("addbanword"))
async def cmd_addbanword(message: Message):
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Использование: <code>/addbanword слово</code>\nДобавляет слово в список запрещённых.")
    word = args[1].strip().lower()
    settings = await get_chat_settings(message.chat.id)
    existing = settings.bad_words if settings and settings.bad_words else ""
    words_list = [w.strip() for w in existing.split(",") if w.strip()] if existing else []
    if word in words_list:
        return await message.answer(f"ℹ️ Слово «{word}» уже в списке.")
    words_list.append(word)
    await update_chat_settings(message.chat.id, bad_words=",".join(words_list), delete_bad_words=True)
    await message.answer(f"✅ Слово «{word}» добавлено в список запрещённых.")


@router.message(Command("delbanword"))
async def cmd_delbanword(message: Message):
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Использование: <code>/delbanword слово</code>")
    word = args[1].strip().lower()
    settings = await get_chat_settings(message.chat.id)
    if not settings or not settings.bad_words:
        return await message.answer("📭 Список запрещённых слов пуст.")
    words_list = [w.strip() for w in settings.bad_words.split(",") if w.strip()]
    if word not in words_list:
        return await message.answer(f"ℹ️ Слово «{word}» не найдено в списке.")
    words_list.remove(word)
    await update_chat_settings(message.chat.id, bad_words=",".join(words_list))
    await message.answer(f"✅ Слово «{word}» удалено из списка запрещённых.")


@router.message(Command("banwords"))
async def cmd_banwords(message: Message):
    settings = await get_chat_settings(message.chat.id)
    if not settings or not settings.bad_words:
        return await message.answer("📭 Список запрещённых слов пуст.")
    words = [w.strip() for w in settings.bad_words.split(",") if w.strip()]
    lines = [f"<b>🤬 Запрещённые слова ({len(words)}):</b>\n"]
    for w in words:
        lines.append(f"• {w}")
    await message.answer("\n".join(lines))


@router.message(Command("addtrigger"))
async def cmd_addtrigger(message: Message):
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer(
            "❌ Использование: <code>/addtrigger слово действие</code>\n"
            "Действия: delete, mute, warn, ban\n"
            "Пример: <code>/addtrigger реклама ban</code>"
        )
    word = parts[1].strip().lower()
    action_str = parts[2].strip().lower()
    action_map = {"delete": TriggerAction.DELETE, "mute": TriggerAction.MUTE, "warn": TriggerAction.WARN, "ban": TriggerAction.BAN}
    action = action_map.get(action_str)
    if not action:
        return await message.answer("❌ Неверное действие. Доступны: delete, mute, warn, ban")
    await add_word_trigger(chat_id=message.chat.id, word=word, action=action, created_by=message.from_user.id)
    await message.answer(f"✅ Триггер добавлен: «{word}» → {action_str}")


@router.message(Command("deltrigger"))
async def cmd_deltrigger(message: Message):
    if not await check_user_can_moderate(message):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Использование: <code>/deltrigger ID</code>\nID можно посмотреть через /triggers")
    try:
        tid = int(args[1])
    except ValueError:
        return await message.answer("❌ Введите числовой ID триггера.")
    ok = await remove_word_trigger(tid)
    if ok:
        await message.answer(f"✅ Триггер #{tid} удалён.")
    else:
        await message.answer("❌ Триггер не найден.")


@router.message(Command("triggers"))
async def cmd_triggers(message: Message):
    triggers = await get_word_triggers(message.chat.id)
    if not triggers:
        return await message.answer("📭 Нет активных триггеров.")
    lines = [f"<b>🎯 Триггеры слов ({len(triggers)}):</b>\n"]
    for t in triggers:
        action_emoji = {"delete": "🗑", "mute": "🔇", "warn": "⚠️", "ban": "🚫", "delete_warn": "🗑⚠️", "delete_mute": "🗑🔇"}
        e = action_emoji.get(t.action.value, "❓")
        lines.append(f"#{t.id} {e} <b>{t.word}</b> → {t.action.value}")
    await message.answer("\n".join(lines))


# ─── Info ────────────────────────────────────────────────────

@router.message(Command("info"))
async def cmd_info(message: Message):
    target = get_target(message) or message.from_user
    user = await get_user(target.id)
    warns = await get_warnings_count(target.id, message.chat.id)
    from bot.database.base import get_session
    from bot.database.models import Punishment as PunModel
    from sqlalchemy import select, and_
    async with get_session() as session:
        active_puns = await session.execute(
            select(PunModel).where(
                and_(PunModel.user_id == target.id, PunModel.chat_id == message.chat.id, PunModel.active.is_(True))
            )
        )
        active = list(active_puns.scalars().all())
    lines = [
        f"<b>👤 Информация о пользователе</b>\n",
        f"ID: <code>{target.id}</code>",
        f"Имя: {target.full_name}",
        f"Баланс: {user.balance:.2f}₽" if user else "Баланс: —",
        f"Варнов: {warns}",
    ]
    if active:
        lines.append(f"\n<b>Активные наказания:</b>")
        for p in active:
            lines.append(f"• {p.type.value}")
    else:
        lines.append(f"\n✅ Активных наказаний нет")
    await message.answer("\n".join(lines))
