from aiogram import Router, F
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func, select

from bot.database.base import get_session
from bot.database.requests import (
    get_or_create_chat, get_chat, get_chat_settings, update_chat_settings,
    get_user, update_user_role,
)
from bot.database.models import User, Chat, Advertisement, AdStatus, UserRole
from bot.filters.admin import IsAdminFilter, IsSuperAdminFilter
from bot.filters.chat_type import IsGroupFilter, IsPrivateFilter
from bot.keyboards.inline import (
    admin_panel_kb, chat_settings_kb, back_kb,
)
from bot.keyboards.reply import admin_menu_kb, remove_kb
from bot.utils.texts import ADMIN_PANEL_TEXT, ADMIN_STATS_TEXT
from bot.loader import config


class SettingsStates(StatesGroup):
    waiting_welcome = State()
    waiting_maxwarns = State()

router = Router()


@router.message(Command("admin"), IsPrivateFilter(), IsAdminFilter())
async def cmd_admin(message: Message):
    await message.answer(ADMIN_PANEL_TEXT, reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin_panel")
async def admin_panel_cb(callback: CallbackQuery):
    await callback.message.edit_text(ADMIN_PANEL_TEXT, reply_markup=admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    async with get_session() as session:
        users_count = (await session.execute(select(func.count(User.id)))).scalar()
        chats_count = (await session.execute(select(func.count(Chat.id)))).scalar()
        ads_total = (await session.execute(select(func.count(Advertisement.id)))).scalar()
        ads_pending = (await session.execute(
            select(func.count(Advertisement.id)).where(Advertisement.status == AdStatus.PENDING)
        )).scalar()
        ads_approved = (await session.execute(
            select(func.count(Advertisement.id)).where(Advertisement.status == AdStatus.APPROVED)
        )).scalar()
        ads_rejected = (await session.execute(
            select(func.count(Advertisement.id)).where(Advertisement.status == AdStatus.REJECTED)
        )).scalar()

    text = ADMIN_STATS_TEXT.format(
        users=users_count or 0,
        chats=chats_count or 0,
        ads_total=ads_total or 0,
        ads_pending=ads_pending or 0,
        ads_approved=ads_approved or 0,
        ads_rejected=ads_rejected or 0,
        total_revenue=0,
    )
    await callback.message.edit_text(text, reply_markup=back_kb("admin_panel"))
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_links"))
async def toggle_links(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    settings = await get_chat_settings(chat_id)
    new_val = not settings.delete_links if settings else True
    await update_chat_settings(chat_id, delete_links=new_val)
    await callback.answer(f"Фильтр ссылок: {'вкл' if new_val else 'выкл'}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=chat_settings_kb(chat_id))


@router.callback_query(F.data.startswith("toggle_badwords"))
async def toggle_badwords(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    settings = await get_chat_settings(chat_id)
    new_val = not settings.delete_bad_words if settings else True
    await update_chat_settings(chat_id, delete_bad_words=new_val)
    await callback.answer(f"Фильтр мата: {'вкл' if new_val else 'выкл'}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=chat_settings_kb(chat_id))


@router.callback_query(F.data.startswith("toggle_captcha"))
async def toggle_captcha(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    settings = await get_chat_settings(chat_id)
    new_val = not settings.captcha_enabled if settings else True
    await update_chat_settings(chat_id, captcha_enabled=new_val)
    await callback.answer(f"Капча: {'вкл' if new_val else 'выкл'}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=chat_settings_kb(chat_id))


@router.callback_query(F.data == "admin_settings")
async def admin_settings_list(callback: CallbackQuery):
    async with get_session() as session:
        result = await session.execute(select(Chat).limit(20))
        chats = list(result.scalars().all())

    if not chats:
        await callback.message.edit_text("Нет доступных чатов.", reply_markup=back_kb("admin_panel"))
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for chat in chats:
        name = chat.title or f"Чат {chat.id}"
        builder.button(text=name, callback_data=f"chat_settings:{chat.id}")
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text("⚙️ <b>Выберите чат для настройки:</b>", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("chat_settings:"))
async def chat_settings_menu(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    chat = await get_chat(chat_id)
    name = chat.title if chat else f"Чат {chat_id}"
    await callback.message.edit_text(
        f"⚙️ <b>Настройки чата: {name}</b>\n\nВыберите параметр для изменения:",
        reply_markup=chat_settings_kb(chat_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_welcome:"))
async def set_welcome_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "✏️ Отправьте текст приветственного сообщения.\n"
        "Используйте <code>{name}</code> для имени пользователя и <code>{chat_title}</code> для названия чата.\n"
        "Или отправьте <code>-</code> чтобы отключить приветствие.",
        reply_markup=back_kb(f"chat_settings:{chat_id}")
    )
    await state.set_state(SettingsStates.waiting_welcome)
    await callback.answer()


@router.message(StateFilter(SettingsStates.waiting_welcome))
async def set_welcome_text(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    text = message.text
    if text == "-":
        await update_chat_settings(chat_id, welcome_enabled=False, welcome_message=None)
        await message.answer("❌ Приветствие отключено.")
    else:
        await update_chat_settings(chat_id, welcome_enabled=True, welcome_message=text)
        await message.answer("✅ Приветствие сохранено!")
    await state.clear()


@router.callback_query(F.data.startswith("set_maxwarns:"))
async def set_maxwarns_start(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "⚠️ Введите максимальное количество варнов до автоматического бана (1-10):",
        reply_markup=back_kb(f"chat_settings:{chat_id}")
    )
    await state.set_state(SettingsStates.waiting_maxwarns)
    await callback.answer()


@router.message(StateFilter(SettingsStates.waiting_maxwarns))
async def set_maxwarns_value(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    try:
        val = int(message.text.strip())
        if 1 <= val <= 10:
            await update_chat_settings(chat_id, max_warns=val)
            await message.answer(f"✅ Максимум варнов установлен: {val}")
        else:
            await message.answer("❌ Введите число от 1 до 10.")
            return
    except (ValueError, TypeError):
        await message.answer("❌ Введите корректное число.")
        return
    await state.clear()


@router.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery):
    async with get_session() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()).limit(20))
        users = list(result.scalars().all())

    lines = ["<b>👥 Последние пользователи:</b>\n"]
    for u in users:
        name = u.first_name or str(u.id)
        lines.append(f"• {name} (@{u.username or '—'}) — <code>{u.role.value}</code> — {u.balance:.2f}₽")
    lines.append(f"\nВсего: {len(users)} показано")

    await callback.message.edit_text("\n".join(lines), reply_markup=back_kb("admin_panel"))
    await callback.answer()
