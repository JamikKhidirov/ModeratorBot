import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.requests import get_chat_settings, update_chat_settings
from bot.keyboards.inline import back_kb

router = Router()


class WelcomeStates(StatesGroup):
    waiting_text = State()
    waiting_photo = State()
    waiting_buttons = State()


WELCOME_PREVIEW_CACHE = {}


@router.callback_query(F.data.startswith("welcome_editor:"))
async def welcome_editor(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    settings = await get_chat_settings(chat_id)

    await state.update_data(chat_id=chat_id)
    text = settings.welcome_message or "Текст приветствия не задан"
    has_photo = bool(settings.welcome_photo)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Текст", callback_data=f"welcome_text:{chat_id}")
    builder.button(text="🖼 Фото", callback_data=f"welcome_photo:{chat_id}")
    builder.button(text="🔘 Кнопки", callback_data=f"welcome_buttons:{chat_id}")
    builder.button(text="👀 Предпросмотр", callback_data=f"welcome_preview:{chat_id}")
    builder.button(text="🔙 Назад", callback_data=f"chat_settings:{chat_id}")
    builder.adjust(2)

    photo_status = "✅ есть" if has_photo else "❌ нет"
    btns_count = 0
    if settings.welcome_buttons:
        try:
            btns_count = len(json.loads(settings.welcome_buttons))
        except Exception:
            pass

    await callback.message.edit_text(
        f"<b>👋 Редактор приветствия</b>\n\n"
        f"📝 Текст: {text[:50]}...\n"
        f"🖼 Фото: {photo_status}\n"
        f"🔘 Кнопок: {btns_count}\n\n"
        f"Выберите, что изменить:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("welcome_text:"))
async def welcome_text_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "✏️ Отправьте новый текст приветствия.\n"
        "Используйте <code>{name}</code> для имени пользователя "
        "и <code>{chat_title}</code> для названия чата.\n\n"
        "Отправьте <code>-</code> чтобы отключить приветствие.",
        reply_markup=back_kb(f"chat_settings:{chat_id}")
    )
    await state.set_state(WelcomeStates.waiting_text)
    await callback.answer()


@router.message(WelcomeStates.waiting_text)
async def welcome_text_save(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    if message.text == "-":
        await update_chat_settings(chat_id, welcome_enabled=False, welcome_message=None)
        await message.answer("❌ Приветствие отключено.")
    else:
        await update_chat_settings(chat_id, welcome_enabled=True, welcome_message=message.text)
        await message.answer("✅ Текст сохранён! Отправьте фото или нажмите /skip")
    await state.clear()


@router.callback_query(F.data.startswith("welcome_photo:"))
async def welcome_photo_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "🖼 Отправьте фото для приветствия\n"
        "или отправьте <code>-</code> чтобы убрать фото.",
        reply_markup=back_kb(f"chat_settings:{chat_id}")
    )
    await state.set_state(WelcomeStates.waiting_photo)
    await callback.answer()


@router.message(WelcomeStates.waiting_photo)
async def welcome_photo_save(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    if message.text == "-":
        await update_chat_settings(chat_id, welcome_photo=None)
        await message.answer("❌ Фото удалено.")
    elif message.photo:
        file_id = message.photo[-1].file_id
        await update_chat_settings(chat_id, welcome_photo=file_id)
        await message.answer("✅ Фото сохранено!")
    else:
        await message.answer("❌ Отправьте фото или <code>-</code>")
        return
    await state.clear()


@router.callback_query(F.data.startswith("welcome_buttons:"))
async def welcome_buttons_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "🔘 <b>Настройка кнопок приветствия</b>\n\n"
        "Отправляйте кнопки в формате:\n"
        "<code>Текст кнопки | https://ссылка</code>\n"
        "Каждая кнопка с новой строки.\n\n"
        "Пример:\n"
        "<code>Наш сайт | https://example.com\n"
        "Правила | https://t.me/username</code>\n\n"
        "Отправьте <code>-</code> чтобы убрать кнопки.",
        reply_markup=back_kb(f"chat_settings:{chat_id}")
    )
    await state.set_state(WelcomeStates.waiting_buttons)
    await callback.answer()


@router.message(WelcomeStates.waiting_buttons)
async def welcome_buttons_save(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    if message.text == "-":
        await update_chat_settings(chat_id, welcome_buttons=None)
        await message.answer("❌ Кнопки удалены.")
        await state.clear()
        return

    buttons = []
    for line in message.text.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 1)
            text = parts[0].strip()
            url = parts[1].strip()
            if text and url.startswith("http"):
                buttons.append({"text": text, "url": url})

    if buttons:
        await update_chat_settings(chat_id, welcome_buttons=json.dumps(buttons))
        await message.answer(f"✅ Сохранено {len(buttons)} кнопок!")
    else:
        await message.answer("❌ Нет корректных кнопок. Формат: <code>Текст | https://ссылка</code>")
        return
    await state.clear()


@router.callback_query(F.data.startswith("welcome_preview:"))
async def welcome_preview(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    settings = await get_chat_settings(chat_id)
    if not settings or not settings.welcome_message:
        await callback.answer("❌ Сначала задайте текст приветствия!", show_alert=True)
        return

    text = settings.welcome_message.format(name="TestUser", chat_title="Test Chat")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if settings.welcome_buttons:
        try:
            btns = json.loads(settings.welcome_buttons)
            for b in btns:
                builder.button(text=b["text"], url=b["url"])
            builder.adjust(1)
        except Exception:
            pass

    try:
        if settings.welcome_photo:
            await callback.message.answer_photo(
                settings.welcome_photo, caption=text,
                reply_markup=builder.as_markup() if btns else None,
            )
        else:
            await callback.message.answer(
                text, reply_markup=builder.as_markup() if btns else None,
            )
    except Exception:
        await callback.message.answer(text)

    await callback.answer("👀 Предпросмотр:")
