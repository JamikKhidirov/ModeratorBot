from datetime import timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatPermissions

from bot.database.requests import (
    add_warning, clear_warnings, get_warnings_count, get_chat_settings,
    add_punishment, deactivate_punishment, get_user,
)
from bot.database.models import PunishmentType
from bot.filters.chat_type import IsGroupFilter
from bot.utils.logger import log_action
from bot.utils.helpers import format_duration, parse_duration, mention_user
from bot.utils.texts import (
    MUTE_SUCCESS, UNMUTE_SUCCESS, BAN_SUCCESS, UNBAN_SUCCESS,
    KICK_SUCCESS, WARN_SUCCESS, WARN_BAN, CLEAR_SUCCESS,
    NO_RIGHTS, NOWARN_TEXT,
)
from bot.utils.helpers import format_duration, parse_duration, mention_user
from bot.keyboards.inline import back_kb

router = Router()
router.message.filter(IsGroupFilter())


async def check_admin_rights(message: Message) -> bool:
    bot_member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
    return bot_member.status in ("administrator", "creator")


async def is_admin_compat(message: Message, user_id: int) -> bool:
    member = await message.chat.get_member(user_id)
    return member.status in ("administrator", "creator")


@router.message(Command("mute"))
async def cmd_mute(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя или укажите @username")

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

    await add_punishment(
        user_id=target.id,
        chat_id=message.chat.id,
        moderator_id=message.from_user.id,
        ptype=PunishmentType.MUTE,
        duration=duration,
        reason=reason,
    )

    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )
    await message.chat.restrict(user_id=target.id, permissions=permissions, until_date=timedelta(seconds=duration))

    name = target.full_name or str(target.id)
    await message.answer(MUTE_SUCCESS.format(user_id=target.id, name=name, duration=format_duration(duration)))
    await log_action(
        message.chat.id, "MUTE",
        message.from_user.full_name, target.full_name,
        reason=reason, duration=format_duration(duration),
    )


@router.message(Command("unmute"))
async def cmd_unmute(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя")

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


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя")

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else None

    await add_punishment(
        user_id=target.id,
        chat_id=message.chat.id,
        moderator_id=message.from_user.id,
        ptype=PunishmentType.BAN,
        reason=reason,
    )
    await message.chat.ban(user_id=target.id)

    name = target.full_name or str(target.id)
    await message.answer(BAN_SUCCESS.format(user_id=target.id, name=name))
    await log_action(message.chat.id, "BAN", message.from_user.full_name, target.full_name, reason=reason)


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя")

    await deactivate_punishment(target.id, message.chat.id, PunishmentType.BAN)
    await message.chat.unban(user_id=target.id)

    name = target.full_name or str(target.id)
    await message.answer(UNBAN_SUCCESS.format(user_id=target.id, name=name))


@router.message(Command("kick"))
async def cmd_kick(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя")

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else None

    await add_punishment(
        user_id=target.id,
        chat_id=message.chat.id,
        moderator_id=message.from_user.id,
        ptype=PunishmentType.KICK,
        reason=reason,
    )
    await message.chat.ban(user_id=target.id)
    await message.chat.unban(user_id=target.id)

    name = target.full_name or str(target.id)
    await message.answer(KICK_SUCCESS.format(user_id=target.id, name=name))
    await log_action(message.chat.id, "KICK", message.from_user.full_name, target.full_name, reason=reason)


@router.message(Command("warn"))
async def cmd_warn(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя")

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else None

    settings = await get_chat_settings(message.chat.id)
    max_warns = settings.max_warns if settings else 3

    warn_count = await add_warning(
        user_id=target.id,
        chat_id=message.chat.id,
        moderator_id=message.from_user.id,
        reason=reason,
    )

    name = target.full_name or str(target.id)
    if warn_count >= max_warns:
        await message.chat.ban(user_id=target.id)
        await clear_warnings(target.id, message.chat.id)
        await message.answer(WARN_BAN.format(user_id=target.id, name=name))
    else:
        await message.answer(
            WARN_SUCCESS.format(
                user_id=target.id, name=name,
                count=warn_count, max=max_warns,
                reason=reason or "Без причины"
            )
        )
        await log_action(message.chat.id, "WARN", message.from_user.full_name, target.full_name, reason=reason)


@router.message(Command("clear"))
async def cmd_clear(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    args = message.text.split()
    count = 10
    if len(args) > 1 and args[1].isdigit():
        count = min(int(args[1]), 100)

    if message.reply_to_message:
        msg_ids = [message.reply_to_message.message_id]
        msg_ids.append(message.message_id)
        try:
            await message.bot.delete_messages(message.chat.id, msg_ids)
        except Exception:
            await message.delete()
        result = await message.answer(CLEAR_SUCCESS.format(count=len(msg_ids)))
    else:
        await message.delete()
        result = await message.answer(CLEAR_SUCCESS.format(count=1))

    import asyncio
    await asyncio.sleep(3)
    try:
        await result.delete()
    except Exception:
        pass


@router.message(Command("warns"))
async def cmd_warns(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    count = await get_warnings_count(target.id, message.chat.id)
    if count == 0:
        return await message.answer(NOWARN_TEXT)
    await message.answer(f"⚠️ Варнов у {target.full_name}: {count}")


@router.message(Command("warnlist"))
async def cmd_warnlist(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
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
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя")
    await clear_warnings(target.id, message.chat.id)
    await message.answer(f"✅ Варны {target.full_name} очищены.")


@router.message(Command("del"))
async def cmd_del(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение для удаления.")
    try:
        await message.reply_to_message.delete()
        await message.delete()
    except Exception:
        await message.answer("❌ Не удалось удалить.")


@router.message(Command("lock"))
async def cmd_lock(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    if not await is_admin_compat(message, message.from_user.id):
        return await message.answer("❌ Только администратор группы может заблокировать чат.")
    try:
        await message.chat.set_permissions(
            ChatPermissions(can_send_messages=False)
        )
        await message.answer("🔒 Чат заблокирован. Только админы могут писать.")
        await log_action(message.chat.id, "LOCK", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав для блокировки чата.")


@router.message(Command("unlock"))
async def cmd_unlock(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    if not await is_admin_compat(message, message.from_user.id):
        return await message.answer("❌ Только администратор группы может разблокировать чат.")
    try:
        await message.chat.set_permissions(
            ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True,
                can_send_polls=True, can_invite_users=True,
            )
        )
        await message.answer("🔓 Чат разблокирован.")
        await log_action(message.chat.id, "UNLOCK", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав для разблокировки чата.")


@router.message(Command("slowmode"))
async def cmd_slowmode(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    args = message.text.split(maxsplit=1)
    seconds = 10
    if len(args) > 1 and args[1].isdigit():
        seconds = min(int(args[1]), 3600)
    try:
        await message.chat.set_slow_mode_delay(seconds)
        await message.answer(f"🐢 Slowmode установлен: {seconds} сек.")
    except Exception:
        await message.answer("❌ Нет прав для установки slowmode.")


@router.message(Command("banlist"))
async def cmd_banlist(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    try:
        count = 0
        async for ban in message.bot.get_chat_administrators(message.chat.id):
            pass
        lines = [f"<b>🚫 Забаненные в {message.chat.title}:</b>\n"]
        lines.append("(Telegram API не предоставляет список забаненных)")
        await message.answer("\n".join(lines))
    except Exception:
        await message.answer("❌ Нет доступа.")


@router.message(Command("kickme"))
async def cmd_kickme(message: Message):
    try:
        await message.chat.ban(message.from_user.id)
        await message.chat.unban(message.from_user.id)
    except Exception:
        await message.answer("❌ Не удалось.")


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
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Использование: /settitle <code>Новый заголовок</code>")
    try:
        await message.chat.set_title(args[1])
        await message.answer(f"✅ Название чата изменено.")
    except Exception:
        await message.answer("❌ Нет прав.")


@router.message(Command("setdescription"))
async def cmd_setdescription(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Использование: /setdescription <code>Текст</code>")
    try:
        await message.chat.set_description(args[1])
        await message.answer(f"✅ Описание чата изменено.")
    except Exception:
        await message.answer("❌ Нет прав.")


@router.message(Command("leave"))
async def cmd_leave(message: Message):
    if not await is_admin_compat(message, message.from_user.id):
        return await message.answer("❌ Только админ может удалить бота.")
    await message.answer("👋 Пока!")
    await message.chat.leave()


@router.message(Command("mute_all"))
async def cmd_mute_all(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    if not await is_admin_compat(message, message.from_user.id):
        return await message.answer("❌ Только администратор группы может замутить всех.")
    try:
        await message.chat.set_permissions(
            ChatPermissions(can_send_messages=False)
        )
        await message.answer("🔇 Все участники замучены.")
        await log_action(message.chat.id, "MUTE_ALL", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав.")


@router.message(Command("unmute_all"))
async def cmd_unmute_all(message: Message):
    if not await check_admin_rights(message):
        return await message.answer(NO_RIGHTS)
    if not await is_admin_compat(message, message.from_user.id):
        return await message.answer("❌ Только администратор группы может размутить всех.")
    try:
        await message.chat.set_permissions(
            ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True,
                can_send_polls=True, can_invite_users=True,
            )
        )
        await message.answer("🔊 Все участники размучены.")
        await log_action(message.chat.id, "UNMUTE_ALL", message.from_user.full_name)
    except Exception:
        await message.answer("❌ Нет прав.")
