from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database.base import get_session
from bot.database.requests import (
    get_chat, update_chat, get_chat_settings, update_chat_settings,
    add_word_trigger, remove_word_trigger, get_word_triggers,
    get_or_create_chat,
)
from bot.database.models import Chat, TriggerAction
from bot.filters.admin import IsAdminFilter
from bot.filters.chat_type import IsGroupFilter, IsPrivateFilter
from bot.keyboards.inline import back_kb


class AdminStates(StatesGroup):
    waiting_badword_add = State()
    waiting_trigger_word = State()
    waiting_trigger_action = State()
    waiting_log_chat = State()
    waiting_auto_delete = State()


router = Router()


# ─── Extended chat settings menu ───────────────────────────

def extended_settings_kb(chat_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="👋 Приветствие (текст)", callback_data=f"set_welcome:{chat_id}")
    builder.button(text="🎨 Приветствие (редактор)", callback_data=f"welcome_editor:{chat_id}")
    builder.button(text="🔗 Ссылки", callback_data=f"toggle_links:{chat_id}")
    builder.button(text="🤬 Мат (словарь)", callback_data=f"badword_menu:{chat_id}")
    builder.button(text="🎯 Триггеры слов", callback_data=f"triggers_menu:{chat_id}")
    builder.button(text="🔒 Капча", callback_data=f"toggle_captcha:{chat_id}")
    builder.button(text="⚠️ Макс. варнов", callback_data=f"set_maxwarns:{chat_id}")
    builder.button(text="🛡️ Анти-рейд", callback_data=f"toggle_raid:{chat_id}")
    builder.button(text="📸 Медиа", callback_data=f"toggle_media:{chat_id}")
    builder.button(text="🎨 Стикеры", callback_data=f"toggle_stickers:{chat_id}")
    builder.button(text="🔇 Тихий режим", callback_data=f"toggle_silent:{chat_id}")
    builder.button(text="📝 Лог-канал", callback_data=f"set_logchat:{chat_id}")
    builder.button(text="🧹 Авто-очистка", callback_data=f"set_autodel:{chat_id}")
    builder.button(text="🔙 Назад", callback_data="admin_settings")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data.startswith("chat_settings:"))
async def chat_settings_extended(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    chat = await get_chat(chat_id)
    name = chat.title if chat else f"Чат {chat_id}"
    await callback.message.edit_text(
        f"⚙️ <b>Полные настройки чата: {name}</b>\n\n"
        "Выберите параметр для настройки:",
        reply_markup=extended_settings_kb(chat_id)
    )
    await callback.answer()


# ─── Toggle anti-raid ──────────────────────────────────────

@router.callback_query(F.data.startswith("toggle_raid:"))
async def toggle_raid(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    chat = await get_chat(chat_id)
    new_val = not chat.anti_raid if chat else True
    await update_chat(chat_id, anti_raid=new_val)
    status = "включён 🛡️" if new_val else "выключен"
    await callback.answer(f"Анти-рейд: {status}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=extended_settings_kb(chat_id))


@router.callback_query(F.data.startswith("toggle_media:"))
async def toggle_media(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    chat = await get_chat(chat_id)
    new_val = not chat.delete_media if chat else True
    await update_chat(chat_id, delete_media=new_val)
    status = "удаление вкл" if new_val else "выкл"
    await callback.answer(f"Фильтр медиа: {status}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=extended_settings_kb(chat_id))


@router.callback_query(F.data.startswith("toggle_stickers:"))
async def toggle_stickers(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    chat = await get_chat(chat_id)
    new_val = not chat.delete_stickers if chat else True
    await update_chat(chat_id, delete_stickers=new_val)
    status = "удаление вкл" if new_val else "выкл"
    await callback.answer(f"Фильтр стикеров: {status}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=extended_settings_kb(chat_id))


@router.callback_query(F.data.startswith("toggle_silent:"))
async def toggle_silent(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    chat = await get_chat(chat_id)
    new_val = not chat.silent_mode if chat else True
    await update_chat(chat_id, silent_mode=new_val)
    status = "включён 🔇" if new_val else "выключен"
    await callback.answer(f"Тихий режим: {status}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=extended_settings_kb(chat_id))


# ─── Log channel setup ─────────────────────────────────────

@router.callback_query(F.data.startswith("set_logchat:"))
async def set_logchat_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "📝 <b>Настройка лог-канала</b>\n\n"
        "Перешлите любое сообщение из канала, куда бот будет отправлять логи действий.\n"
        "Бот должен быть администратором в этом канале.\n\n"
        "Или отправьте <code>-</code> чтобы отключить логирование.",
        reply_markup=back_kb(f"chat_settings:{chat_id}")
    )
    await state.set_state(AdminStates.waiting_log_chat)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_log_chat))
async def set_logchat_value(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]

    if message.text and message.text.strip() == "-":
        await update_chat(chat_id, log_chat_id=None)
        await message.answer("❌ Логирование отключено.")
        await state.clear()
        return

    if message.forward_from_chat:
        log_chat_id = message.forward_from_chat.id
        await update_chat(chat_id, log_chat_id=log_chat_id)
        await message.answer(
            f"✅ Лог-канал установлен: {message.forward_from_chat.title}\n"
            f"ID: <code>{log_chat_id}</code>"
        )
    else:
        await message.answer(
            "❌ Пожалуйста, перешлите сообщение из канала.\n"
            "Отправьте <code>-</code> чтобы отключить."
        )
        return
    await state.clear()


# ─── Bad words dictionary management ───────────────────────

@router.callback_query(F.data.startswith("badword_menu:"))
async def badword_menu(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    settings = await get_chat_settings(chat_id)
    words = settings.bad_words.split(",") if settings and settings.bad_words else []

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить слово", callback_data=f"badword_add:{chat_id}")
    if words:
        for i, w in enumerate(words[:10]):
            builder.button(text=f"❌ {w.strip()[:15]}", callback_data=f"badword_del:{chat_id}:{i}")
    builder.button(text="🔙 Назад", callback_data=f"chat_settings:{chat_id}")
    builder.adjust(2)

    text = "<b>📖 Словарь запрещённых слов</b>\n\n"
    if words:
        text += "Текущие слова:\n" + "\n".join(f"• <code>{w.strip()}</code>" for w in words[:20])
    else:
        text += "Список пуст. Нажмите «Добавить слово»."
    if len(words) > 20:
        text += f"\n...и ещё {len(words) - 20}"

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("badword_add:"))
async def badword_add_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "✏️ Отправьте слово (или несколько через запятую) для добавления в чёрный список:",
        reply_markup=back_kb(f"badword_menu:{chat_id}")
    )
    await state.set_state(AdminStates.waiting_badword_add)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_badword_add))
async def badword_add_process(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    new_words = message.text.strip().lower()

    settings = await get_chat_settings(chat_id)
    existing = settings.bad_words.split(",") if settings and settings.bad_words else []
    existing = [w.strip() for w in existing if w.strip()]

    for w in new_words.split(","):
        w = w.strip()
        if w and w not in existing:
            existing.append(w)

    await update_chat_settings(chat_id, bad_words=",".join(existing))
    await message.answer(f"✅ Добавлено слов: {len(new_words.split(','))}")
    await state.clear()


@router.callback_query(F.data.startswith("badword_del:"))
async def badword_del(callback: CallbackQuery):
    parts = callback.data.split(":")
    chat_id = int(parts[1])
    idx = int(parts[2])

    settings = await get_chat_settings(chat_id)
    words = settings.bad_words.split(",") if settings and settings.bad_words else []
    words = [w.strip() for w in words if w.strip()]

    if 0 <= idx < len(words):
        removed = words.pop(idx)
        await update_chat_settings(chat_id, bad_words=",".join(words))
        await callback.answer(f"✅ Слово «{removed}» удалено", show_alert=True)
    else:
        await callback.answer("❌ Слово не найдено", show_alert=True)

    await badword_menu(callback)


# ─── Word triggers management ──────────────────────────────

@router.callback_query(F.data.startswith("triggers_menu:"))
async def triggers_menu(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    triggers = await get_word_triggers(chat_id)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Новый триггер", callback_data=f"trigger_add:{chat_id}")
    for t in triggers[:10]:
        builder.button(
            text=f"❌ {t.word[:12]} → {t.action.value}",
            callback_data=f"trigger_del:{t.id}"
        )
    builder.button(text="🔙 Назад", callback_data=f"chat_settings:{chat_id}")
    builder.adjust(2)

    text = "<b>🎯 Триггеры слов</b>\n\n"
    if triggers:
        for t in triggers[:20]:
            action_emoji = {"delete": "🗑", "mute": "🔇", "warn": "⚠️", "ban": "🚫", "delete_warn": "⚠️🗑", "delete_mute": "🔇🗑"}
            emoji = action_emoji.get(t.action.value, "⚡")
            text += f"{emoji} <code>{t.word}</code> → {t.action.value}\n"
    else:
        text += "Нет триггеров. Нажмите «Новый триггер»."

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("trigger_add:"))
async def trigger_add_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "🎯 <b>Создание триггера</b>\n\n"
        "Отправьте слово, на которое бот будет реагировать:",
        reply_markup=back_kb(f"triggers_menu:{chat_id}")
    )
    await state.set_state(AdminStates.waiting_trigger_word)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_trigger_word))
async def trigger_word_received(message: Message, state: FSMContext):
    word = message.text.strip().lower()
    await state.update_data(word=word)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    actions = [
        ("🗑 Удалить", "delete"),
        ("🔇 Замутить", "mute"),
        ("⚠️ Варн", "warn"),
        ("🚫 Бан", "ban"),
        ("⚠️ Варн+удалить", "delete_warn"),
        ("🔇 Мут+удалить", "delete_mute"),
    ]
    for label, action in actions:
        builder.button(text=label, callback_data=f"trigger_action:{action}")
    builder.adjust(2)

    await message.answer(
        f"🎯 Выберите действие для триггера «<code>{word}</code>»:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdminStates.waiting_trigger_action)


@router.callback_query(F.data.startswith("trigger_action:"), StateFilter(AdminStates.waiting_trigger_action))
async def trigger_action_chosen(callback: CallbackQuery, state: FSMContext):
    action_str = callback.data.split(":")[1]
    action = TriggerAction(action_str)
    data = await state.get_data()

    await add_word_trigger(
        chat_id=data["chat_id"],
        word=data["word"],
        action=action,
        created_by=callback.from_user.id,
    )
    await callback.message.edit_text(
        f"✅ Триггер создан!\n"
        f"Слово: <code>{data['word']}</code>\n"
        f"Действие: {action.value}",
    )
    await state.clear()
    await callback.answer("✅ Триггер создан", show_alert=True)


@router.callback_query(F.data.startswith("trigger_del:"))
async def trigger_del(callback: CallbackQuery):
    tid = int(callback.data.split(":")[1])
    removed = await remove_word_trigger(tid)
    await callback.answer("✅ Триггер удалён" if removed else "❌ Не найден", show_alert=True)
    await callback.message.delete()


# ─── Pin / Unpin ───────────────────────────────────────────

# ─── Auto-delete time setting ──────────────────────────────

@router.callback_query(F.data.startswith("set_autodel:"))
async def set_autodel_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    settings = await get_chat_settings(chat_id)
    current_hours = settings.auto_delete_time if settings else 0
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        f"🧹 <b>Авто-очистка сообщений</b>\n\n"
        f"Сейчас: {current_hours} ч. (0 — отключено)\n\n"
        "Введите количество часов, через которое бот будет авто-удалять "
        "свои сообщения (реклама, уведомления).\n"
        "Например: <code>24</code>, <code>48</code>, <code>72</code>\n"
        "Отправьте <code>0</code> чтобы отключить.",
        reply_markup=back_kb(f"chat_settings:{chat_id}")
    )
    await state.set_state(AdminStates.waiting_auto_delete)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_auto_delete))
async def set_autodel_value(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    try:
        hours = int(message.text.strip())
        if hours < 0:
            raise ValueError
        await update_chat_settings(chat_id, auto_delete_time=hours)
        status = f"✅ Авто-очистка: {hours} ч." if hours > 0 else "❌ Авто-очистка отключена"
        await message.answer(status)
    except (ValueError, TypeError):
        await message.answer("❌ Введите целое число часов (0 — отключить).")
        return
    await state.clear()


@router.message(Command("pin"), IsGroupFilter())
async def cmd_pin(message: Message):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение для закрепления.")
    try:
        await message.reply_to_message.pin(disable_notification=True)
        await message.delete()
    except Exception:
        await message.answer("❌ Нет прав для закрепления.")


@router.message(Command("unpin"), IsGroupFilter())
async def cmd_unpin(message: Message):
    try:
        if message.reply_to_message:
            await message.reply_to_message.unpin()
        else:
            await message.chat.unpin_all_messages()
        await message.delete()
    except Exception:
        await message.answer("❌ Нет прав для открепления.")
