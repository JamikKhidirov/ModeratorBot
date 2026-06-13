from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.models import UserRole
from bot.database.requests import (
    get_user, get_or_create_user, create_giveaway, update_giveaway_message,
    get_active_giveaways, get_giveaway, add_giveaway_participant,
    get_giveaway_participants, set_participant_repost_verified,
    is_chat_admin_assigned,
)
from bot.filters.chat_type import IsGroupFilter, IsPrivateFilter
from bot.keyboards.inline import giveaway_join_kb, back_kb
from bot.utils.texts import GIVEAWAY_CREATED_TEXT, GIVEAWAY_JOINED_TEXT

router = Router()
router.message.filter(IsGroupFilter())

repost_router = Router()  # for private chat repost verification


class GiveawayStates(StatesGroup):
    entering_title = State()
    entering_prize = State()
    entering_description = State()
    entering_winners = State()
    choosing_conditions = State()
    entering_channels = State()
    choosing_repost = State()
    entering_repost_message = State()
    entering_duration = State()
    confirming = State()


async def can_create_giveaway(user_id: int, chat_id: int) -> bool:
    user = await get_user(user_id)
    if user and user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        return True
    return await is_chat_admin_assigned(user_id, chat_id)


@router.message(Command("giveaway"))
async def cmd_giveaway(message: Message, state: FSMContext):
    if not await can_create_giveaway(message.from_user.id, message.chat.id):
        return await message.answer("❌ Только администраторы могут создавать розыгрыши.")
    await state.update_data(chat_id=message.chat.id, creator_id=message.from_user.id)
    await message.answer("🎁 <b>Создание розыгрыша</b>\n\nВведите <b>название</b> розыгрыша:")
    await state.set_state(GiveawayStates.entering_title)


@router.message(GiveawayStates.entering_title)
async def giveaway_title(message: Message, state: FSMContext):
    if len(message.text) > 256:
        return await message.answer("❌ Название слишком длинное (макс. 256 символов).")
    await state.update_data(title=message.text)
    await message.answer("🎁 <b>Приз</b>\n\nОпишите <b>приз</b> розыгрыша (что разыгрывается):")
    await state.set_state(GiveawayStates.entering_prize)


@router.message(GiveawayStates.entering_prize)
async def giveaway_prize(message: Message, state: FSMContext):
    await state.update_data(prize=message.text)
    await message.answer(
        "📝 <b>Описание (необязательно)</b>\n\n"
        "Добавьте описание или условия участия.\n"
        "Или отправьте <code>-</code> чтобы пропустить."
    )
    await state.set_state(GiveawayStates.entering_description)


@router.message(GiveawayStates.entering_description)
async def giveaway_description(message: Message, state: FSMContext):
    desc = None if message.text == "-" else message.text
    await state.update_data(description=desc)
    await message.answer(
        "👥 <b>Количество победителей</b>\n\n"
        "Сколько человек выиграют? (1-10)"
    )
    await state.set_state(GiveawayStates.entering_winners)


@router.message(GiveawayStates.entering_winners)
async def giveaway_winners(message: Message, state: FSMContext):
    try:
        n = int(message.text.strip())
        if n < 1 or n > 10:
            raise ValueError
    except (ValueError, TypeError):
        return await message.answer("❌ Введите число от 1 до 10.")
    await state.update_data(winners=n)
    await message.answer(
        "🔒 <b>Условия участия</b>\n\n"
        "Нужна ли подписка на канал? Отправьте ID канала (например <code>-1001234567890</code>)\n"
        "Если не нужно — отправьте <code>-</code>.\n"
        "Можно указать несколько через запятую."
    )
    await state.set_state(GiveawayStates.entering_channels)


@router.message(GiveawayStates.entering_channels)
async def giveaway_channels(message: Message, state: FSMContext):
    if message.text == "-":
        await state.update_data(require_channels=None)
    else:
        channels = message.text.strip()
        await state.update_data(require_channels=channels)
    await message.answer(
        "🔄 <b>Репост</b>\n\n"
        "Требовать ли репост? Отправьте <code>да</code> или <code>нет</code>.\n"
        "Если да — нужно будет переслать сообщение боту для проверки."
    )
    await state.set_state(GiveawayStates.choosing_repost)


@router.message(GiveawayStates.choosing_repost)
async def giveaway_repost(message: Message, state: FSMContext):
    if message.text.lower() in ("да", "yes"):
        await state.update_data(require_repost=True)
        await message.answer(
            "🔄 <b>Сообщение для репоста</b>\n\n"
            "Перешлите боту в ЛС сообщение, которое нужно репостнуть.\n"
            "Это может быть пост из вашего канала."
        )
        await state.set_state(GiveawayStates.entering_repost_message)
    else:
        await state.update_data(require_repost=False, repost_channel_id=None, repost_message_id=None)
        await ask_duration(message, state)


@router.message(GiveawayStates.entering_repost_message, IsPrivateFilter())
async def giveaway_repost_message(message: Message, state: FSMContext):
    fwd = message.forward_from_chat or (message.forward_from and message.forward_from.id)
    if not fwd or not message.forward_from_message_id:
        return await message.answer(
            "❌ Пожалуйста, перешлите сообщение (не просто текст).\n"
            "Откройте канал, найдите пост и нажмите «Переслать»."
        )
    await state.update_data(
        repost_channel_id=message.forward_from_chat.id if message.forward_from_chat else None,
        repost_message_id=message.forward_from_message_id,
    )
    await message.answer("✅ Сообщение сохранено!")
    await ask_duration(message, state)


async def ask_duration(message: Message, state: FSMContext):
    await message.answer(
        "⏰ <b>Длительность</b>\n\n"
        "Через сколько завершить розыгрыш?\n"
        "Примеры: <code>1ч</code>, <code>24ч</code>, <code>3д</code>, <code>7д</code>"
    )
    await state.set_state(GiveawayStates.entering_duration)


@router.message(GiveawayStates.entering_duration)
async def giveaway_duration(message: Message, state: FSMContext):
    seconds = parse_giveaway_duration(message.text)
    if not seconds:
        return await message.answer(
            "❌ Некорректный формат. Примеры: <code>1ч</code>, <code>24ч</code>, <code>3д</code>, <code>7д</code>"
        )
    ends_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    await state.update_data(ends_at=ends_at)

    data = await state.get_data()
    channels_text = data.get("require_channels", "—") or "Не требуется"
    lines = [
        "🎁 <b>Подтверждение розыгрыша</b>\n",
        f"📌 Название: {data['title']}",
        f"🎁 Приз: {data['prize']}",
    ]
    if data.get("description"):
        lines.append(f"📝 Описание: {data['description']}")
    lines.append(f"👥 Победителей: {data['winners']}")
    lines.append(f"🔒 Каналы: {channels_text}")
    lines.append(f"🔄 Репост: {'Да' if data.get('require_repost') else 'Нет'}")
    lines.append(f"⏰ Завершится: {ends_at.strftime('%d.%m.%Y %H:%M')} UTC\n")
    lines.append("Всё верно?")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать", callback_data="giveaway_confirm")
    builder.button(text="❌ Отмена", callback_data="giveaway_cancel")
    builder.adjust(2)
    await message.answer("\n".join(lines), reply_markup=builder.as_markup())
    await state.set_state(GiveawayStates.confirming)


@router.callback_query(F.data == "giveaway_confirm", GiveawayStates.confirming)
async def giveaway_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    g = await create_giveaway(
        chat_id=data["chat_id"],
        creator_id=data["creator_id"],
        title=data["title"],
        prize=data["prize"],
        description=data.get("description"),
        winners_count=data["winners"],
        ends_at=data["ends_at"],
        require_channels=data.get("require_channels"),
        require_repost=data.get("require_repost", False),
        repost_channel_id=data.get("repost_channel_id"),
        repost_message_id=data.get("repost_message_id"),
    )

    text = GIVEAWAY_CREATED_TEXT.format(
        title=g.title, prize=g.prize, desc=g.description or "",
        winners=g.winners_count,
        channels=g.require_channels or "Не требуется",
        repost="Да" if g.require_repost else "Нет",
        ends=g.ends_at.strftime("%d.%m.%Y %H:%M"),
    )
    msg = await callback.message.answer(text, reply_markup=giveaway_join_kb(g.id))
    await update_giveaway_message(g.id, msg.message_id)
    await callback.message.delete()
    await callback.answer("✅ Розыгрыш создан!")
    await state.clear()


@router.callback_query(F.data == "giveaway_cancel", GiveawayStates.confirming)
async def giveaway_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Создание розыгрыша отменено.")
    await callback.answer()
    await state.clear()


@router.callback_query(F.data.startswith("giveaway_join:"))
async def giveaway_join(callback: CallbackQuery):
    giveaway_id = int(callback.data.split(":")[1])
    g = await get_giveaway(giveaway_id)
    if not g or g.status != "active":
        return await callback.answer("❌ Розыгрыш уже завершён.", show_alert=True)

    if g.ends_at <= datetime.now(timezone.utc):
        return await callback.answer("❌ Розыгрыш уже завершён.", show_alert=True)

    if g.require_channels:
        channels = [c.strip() for c in g.require_channels.split(",")]
        for ch_id_str in channels:
            try:
                ch_id = int(ch_id_str)
                member = await callback.bot.get_chat_member(ch_id, callback.from_user.id)
                if member.status not in ("member", "administrator", "creator"):
                    name = (await callback.bot.get_chat(ch_id)).title or ch_id
                    return await callback.answer(
                        f"❌ Вы не подписаны на канал «{name}».\nПодпишитесь и попробуйте снова.",
                        show_alert=True,
                    )
            except Exception:
                return await callback.answer("❌ Ошибка проверки подписки.", show_alert=True)

    if g.require_repost:
        already = await get_giveaway_participants(giveaway_id)
        if any(p.user_id == callback.from_user.id and p.repost_verified for p in already):
            pass
        else:
            return await callback.answer(
                "🔄 Для участия нужно переслать сообщение боту.\n"
                "Напишите боту в ЛС и перешлите то сообщение, которое указано в розыгрыше.",
                show_alert=True,
            )

    ok = await add_giveaway_participant(giveaway_id, callback.from_user.id)
    if not ok:
        return await callback.answer("ℹ️ Вы уже участвуете в этом розыгрыше!", show_alert=True)

    await callback.answer(GIVEAWAY_JOINED_TEXT, show_alert=True)

    count = len(await get_giveaway_participants(giveaway_id))
    try:
        await callback.bot.edit_message_reply_markup(
            g.chat_id, g.message_id,
            reply_markup=giveaway_join_kb(giveaway_id, count),
        )
    except Exception:
        pass


@router.message(Command("giveaways"))
async def cmd_giveaways(message: Message):
    giveaways = await get_active_giveaways(message.chat.id)
    if not giveaways:
        return await message.answer("📭 В этом чате нет активных розыгрышей.")

    lines = ["<b>🎁 Активные розыгрыши:</b>\n"]
    for g in giveaways:
        participants = await get_giveaway_participants(g.id)
        lines.append(
            f"• #{g.id} <b>{g.title}</b> — {g.prize}\n"
            f"  👥 Участников: {len(participants)} | ⏰ до {g.ends_at.strftime('%d.%m %H:%M')}\n"
        )
    await message.answer("\n".join(lines))


@router.message(Command("cancelgiveaway"))
async def cmd_cancel_giveaway(message: Message):
    if not await can_create_giveaway(message.from_user.id, message.chat.id):
        return await message.answer("❌ Нет доступа.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ Укажите ID розыгрыша: /cancelgiveaway <id>")
    try:
        gid = int(args[1])
    except ValueError:
        return await message.answer("❌ Некорректный ID.")
    from bot.database.requests import cancel_giveaway
    g = await get_giveaway(gid)
    if not g or g.chat_id != message.chat.id:
        return await message.answer("❌ Розыгрыш не найден.")
    if g.status != "active":
        return await message.answer("❌ Розыгрыш уже завершён.")
    await cancel_giveaway(gid)
    await message.answer(f"❌ Розыгрыш #{gid} отменён.")
    try:
        await message.bot.edit_message_text(
            f"❌ <b>Розыгрыш отменён</b>\n\n{g.title}\n🎁 {g.prize}",
            g.chat_id, g.message_id,
        )
    except Exception:
        pass


def parse_giveaway_duration(text: str) -> int | None:
    text = text.lower().strip()
    try:
        if text.endswith("д"):
            return int(text[:-1]) * 86400
        if text.endswith("ч"):
            return int(text[:-1]) * 3600
        if text.endswith("м"):
            return int(text[:-1]) * 60
        if text.isdigit():
            return int(text) * 3600
    except (ValueError, TypeError):
        return None
    return None


# ─── PM Repost Verification ─────────────────────────────────

@repost_router.message(F.forward_from_chat | F.forward_from, IsPrivateFilter())
async def giveaway_repost_verify(message: Message):
    fwd_chat = message.forward_from_chat
    fwd_msg_id = message.forward_from_message_id
    if not fwd_chat or not fwd_msg_id:
        return await message.answer(
            "❌ Не удалось проверить пересланное сообщение.\n"
            "Перешлите сообщение из канала напрямую."
        )

    active = await get_active_giveaways()
    for g in active:
        if not g.require_repost:
            continue
        if g.repost_channel_id == fwd_chat.id and g.repost_message_id == fwd_msg_id:
            participants = await get_giveaway_participants(g.id)
            already = any(p.user_id == message.from_user.id for p in participants)
            if already:
                continue
            await set_participant_repost_verified(g.id, message.from_user.id)
            await add_giveaway_participant(g.id, message.from_user.id)
            text = (
                f"✅ <b>Репост подтверждён!</b>\n"
                f"Вы участвуете в розыгрыше «{g.title}»!\n\n"
                f"🎁 Приз: {g.prize}"
            )
            await message.answer(text)

            count = len(await get_giveaway_participants(g.id))
            try:
                await message.bot.edit_message_reply_markup(
                    g.chat_id, g.message_id,
                    reply_markup=giveaway_join_kb(g.id, count),
                )
            except Exception:
                pass
            return

    await message.answer(
        "❌ Не найден активный розыгрыш, соответствующий этому сообщению.\n"
        "Проверьте, что вы пересылаете правильное сообщение."
    )
