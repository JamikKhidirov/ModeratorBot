from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.requests import (
    create_recurring_post, get_recurring_posts, delete_recurring_post, get_chat,
)
from bot.filters.admin import IsAdminFilter
from bot.filters.chat_type import IsGroupFilter

router = Router()


class RecurringStates(StatesGroup):
    waiting_text = State()
    waiting_time = State()


DAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


@router.message(Command("recurring"), IsGroupFilter())
async def cmd_recurring(message: Message):
    posts = await get_recurring_posts(message.chat.id)
    if not posts:
        await message.answer(
            "📭 Нет регулярных постов в этом чате.\n"
            "Создайте: /recurring_add"
        )
        return

    lines = [f"<b>📅 Регулярные посты в {message.chat.title}:</b>\n"]
    for i, p in enumerate(posts, 1):
        day_str = DAYS[p.day_of_week] if p.day_of_week is not None else f"каждые {p.interval_days} дн."
        time_str = f"{p.hour:02d}:{p.minute:02d}"
        text_preview = (p.text or "")[:30]
        lines.append(f"{i}. {day_str} {time_str} — <code>{text_preview}...</code>")
    lines.append("\n/recurring_add — создать\n/recurring_del <code>id</code> — удалить")

    await message.answer("\n".join(lines))


@router.message(Command("recurring_add"), IsGroupFilter())
async def recurring_add_start(message: Message, state: FSMContext):
    await state.update_data(chat_id=message.chat.id)
    await message.answer(
        "📅 <b>Новый регулярный пост</b>\n\n"
        "Отправьте текст сообщения (можно с фото/видео):",
    )
    await state.set_state(RecurringStates.waiting_text)


@router.message(RecurringStates.waiting_text)
async def recurring_text_received(message: Message, state: FSMContext):
    text = message.text or message.caption
    media = None
    media_type = None
    if message.photo:
        media = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media = message.video.file_id
        media_type = "video"

    await state.update_data(text=text, media=media, media_type=media_type)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for i, d in enumerate(DAYS):
        builder.button(text=d, callback_data=f"rec_day:{i}")
    builder.button(text="Каждый день", callback_data="rec_day:every")
    builder.button(text="Каждые N дней", callback_data="rec_day:interval")
    builder.adjust(7, 1, 1)

    await message.answer(
        "📅 Выберите день недели или интервал:", reply_markup=builder.as_markup()
    )
    await state.set_state(RecurringStates.waiting_time)


@router.callback_query(F.data.startswith("rec_day:"))
async def recurring_day_chosen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    val = callback.data.split(":")[1]

    if val == "every":
        await state.update_data(day_of_week=None, interval_days=1)
    elif val == "interval":
        await callback.message.edit_text("Введите интервал в днях (число):")
        await state.set_state(RecurringStates.waiting_time)
        await callback.answer()
        return
    else:
        await state.update_data(day_of_week=int(val), interval_days=None)

    await callback.message.edit_text(
        "🕐 Введите время в формате <code>ЧЧ:ММ</code> (например 10:00):"
    )
    await state.set_state(RecurringStates.waiting_time)
    await callback.answer()


@router.message(RecurringStates.waiting_time)
async def recurring_time_received(message: Message, state: FSMContext):
    data = await state.get_data()

    if "interval_days" not in data and ":" in message.text:
        try:
            parts = message.text.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            await message.answer("❌ Неверный формат. Используйте ЧЧ:ММ")
            return
        await state.update_data(hour=hour, minute=minute)
    elif message.text.strip().isdigit():
        await state.update_data(interval_days=int(message.text.strip()), day_of_week=None, hour=12, minute=0)
    else:
        await message.answer("❌ Введите время ЧЧ:ММ или число дней.")
        return

    d = await state.get_data()
    await create_recurring_post(
        chat_id=d["chat_id"], text=d.get("text"), hour=d.get("hour", 12),
        minute=d.get("minute", 0), day_of_week=d.get("day_of_week"),
        interval_days=d.get("interval_days"),
        media=d.get("media"), media_type=d.get("media_type"),
        created_by=message.from_user.id,
    )
    await message.answer("✅ Регулярный пост создан!")
    await state.clear()


@router.message(Command("recurring_del"), IsGroupFilter())
async def recurring_del(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Использование: /recurring_del <code>ID</code>")
        return
    deleted = await delete_recurring_post(int(args[1]))
    await message.answer("✅ Удалено" if deleted else "❌ Не найдено")
