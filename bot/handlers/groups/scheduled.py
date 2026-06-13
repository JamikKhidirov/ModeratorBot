from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.requests import (
    create_scheduled_message, get_user_scheduled, cancel_scheduled,
)
from bot.filters.admin import IsAdminFilter
from bot.filters.chat_type import IsGroupFilter, IsPrivateFilter
from bot.keyboards.inline import back_kb
from bot.utils.helpers import parse_duration

router = Router()


class ScheduleStates(StatesGroup):
    waiting_text = State()
    waiting_time = State()


@router.message(Command("schedule"), IsGroupFilter())
async def cmd_schedule(message: Message, state: FSMContext):
    await message.answer(
        "⏰ <b>Отложенное сообщение</b>\n\n"
        "Отправьте текст сообщения, которое хотите запланировать:\n"
        "(можно с фото или видео)",
        reply_markup=back_kb("schedule_cancel")
    )
    await state.set_state(ScheduleStates.waiting_text)


@router.callback_query(F.data == "schedule_cancel")
async def schedule_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отложенное сообщение отменено.")
    await callback.answer()


@router.message(ScheduleStates.waiting_text)
async def schedule_text_received(message: Message, state: FSMContext):
    text = message.text or message.caption
    if not text:
        await message.answer("❌ Текст не может быть пустым.")
        return

    media = None
    media_type = None
    if message.photo:
        media = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media = message.video.file_id
        media_type = "video"

    await state.update_data(text=text, media=media, media_type=media_type)
    await message.answer(
        "⏰ <b>Когда отправить?</b>\n\n"
        "Укажите время в одном из форматов:\n"
        "• <code>30м</code> — через 30 минут\n"
        "• <code>2ч</code> — через 2 часа\n"
        "• <code>1д</code> — через 1 день\n"
        "• <code>2026-06-14 15:00</code> — точная дата\n\n"
        "Или отправьте <code>-</code> для отмены.",
        reply_markup=back_kb("schedule_cancel")
    )
    await state.set_state(ScheduleStates.waiting_time)


@router.message(ScheduleStates.waiting_time)
async def schedule_time_received(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "-":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    now = datetime.now(timezone.utc)
    send_at = None

    seconds = parse_duration(text)
    if seconds:
        send_at = now + timedelta(seconds=seconds)
    else:
        try:
            send_at = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                send_at = datetime.strptime(text, "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
            except ValueError:
                await message.answer(
                    "❌ Неверный формат. Используйте:\n"
                    "<code>30м</code>, <code>2ч</code>, <code>1д</code> или <code>2026-06-14 15:00</code>"
                )
                return

    if send_at <= now:
        await message.answer("❌ Время должно быть в будущем.")
        return

    data = await state.get_data()
    sch = await create_scheduled_message(
        chat_id=message.chat.id,
        text=data["text"],
        send_at=send_at,
        created_by=message.from_user.id,
        media=data.get("media"),
        media_type=data.get("media_type"),
    )

    await message.answer(
        f"✅ <b>Сообщение запланировано!</b>\n\n"
        f"🆔 ID: <code>{sch.id}</code>\n"
        f"⏰ Отправка: {send_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"💬 Чат: {message.chat.title}"
    )
    await state.clear()


@router.message(Command("scheduled"))
async def cmd_scheduled(message: Message):
    scheds = await get_user_scheduled(message.from_user.id)
    if not scheds:
        await message.answer("📭 У вас нет запланированных сообщений.")
        return

    lines = ["<b>📋 Запланированные сообщения:</b>\n"]
    for s in scheds:
        lines.append(
            f"• <code>#{s.id}</code> | {s.send_at.strftime('%d.%m %H:%M')} "
            f"| {(s.text or '')[:30]}..."
        )
    lines.append("\n/cancel_schedule <code>ID</code> — отменить")

    await message.answer("\n".join(lines))


@router.message(Command("cancel_schedule"))
async def cmd_cancel_schedule(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Использование: /cancel_schedule <code>ID</code>")
        return

    msg_id = int(args[1])
    cancelled = await cancel_scheduled(msg_id)
    if cancelled:
        await message.answer(f"✅ Сообщение #{msg_id} отменено.")
    else:
        await message.answer(f"❌ Сообщение #{msg_id} не найдено или уже отправлено.")
