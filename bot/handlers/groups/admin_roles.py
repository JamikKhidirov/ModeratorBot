from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database.base import get_session
from bot.database.requests import (
    get_user, update_user_role, get_users_by_role, get_all_admins,
    add_group_moderator, remove_group_moderator, get_group_moderators,
    get_or_create_user,
)
from bot.database.models import User, GroupModerator, UserRole
from bot.filters.admin import IsAdminFilter, IsSuperAdminFilter
from bot.filters.chat_type import IsPrivateFilter, IsGroupFilter
from bot.keyboards.inline import back_kb, admin_panel_kb
from bot.utils.texts import (
    ADMIN_LIST_HEADER, ADMIN_LIST_ITEM, NO_ADMINS,
    MOD_LIST_HEADER, MOD_LIST_ITEM, NO_MODS,
    ADMIN_ADDED, ADMIN_REMOVED, MOD_ADDED, MOD_REMOVED,
    CANT_REMOVE_SELF, USER_NOT_FOUND_ERR, ALREADY_ADMIN, ALREADY_MOD,
    NOT_ADMIN, NOT_MOD,
)
from bot.loader import config

router = Router()


class RoleStates(StatesGroup):
    waiting_user_for_admin = State()
    waiting_user_for_mod = State()
    waiting_user_remove_admin = State()
    waiting_user_remove_mod = State()


# ─── Bot-wide Admin Management (via /admin panel) ────────────

@router.callback_query(F.data == "admin_roles", IsAdminFilter())
async def admin_roles_menu(callback: CallbackQuery):
    builder = get_roles_kb()
    await callback.message.edit_text(
        "👑 <b>Управление администраторами</b>\n\n"
        "• <b>Администраторы</b> — полный доступ к панели\n"
        "• <b>Модераторы</b> — модерация в группах\n"
        "• <b>СуперАдмины</b> — полный доступ + управление админами\n\n"
        "Выберите действие:",
        reply_markup=builder
    )
    await callback.answer()


def get_roles_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Список администраторов", callback_data="list_admins")
    builder.button(text="➕ Добавить администратора", callback_data="add_admin_start")
    builder.button(text="➖ Удалить администратора", callback_data="remove_admin_start")
    builder.button(text="📋 Список модераторов", callback_data="list_mods")
    builder.button(text="➕ Добавить модератора", callback_data="add_mod_start")
    builder.button(text="➖ Удалить модератора", callback_data="remove_mod_start")
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()


# ─── List Admins ─────────────────────────────────────────────

@router.callback_query(F.data == "list_admins", IsAdminFilter())
async def list_admins(callback: CallbackQuery):
    admins = await get_all_admins()
    if not admins:
        await callback.message.edit_text(NO_ADMINS, reply_markup=back_kb("admin_roles"))
        await callback.answer()
        return

    superadmin_ids = set(config.admin_ids)
    lines = [ADMIN_LIST_HEADER]
    for a in admins:
        name = a.first_name or str(a.id)
        is_super = "👑" if a.id in superadmin_ids else ""
        lines.append(
            ADMIN_LIST_ITEM.format(
                emoji="👑" if a.role == UserRole.SUPERADMIN else "🛡️",
                name=name,
                username=a.username or "—",
                user_id=a.id,
                role=a.role.value,
                super_emoji=is_super,
            )
        )
    await callback.message.edit_text("\n".join(lines), reply_markup=back_kb("admin_roles"))
    await callback.answer()


# ─── Add Admin ───────────────────────────────────────────────

@router.callback_query(F.data == "add_admin_start", IsSuperAdminFilter())
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "👑 <b>Добавление администратора</b>\n\n"
        "Отправьте ID или @username пользователя, "
        "которому хотите выдать права администратора:",
        reply_markup=back_kb("admin_roles")
    )
    await state.set_state(RoleStates.waiting_user_for_admin)
    await callback.answer()


@router.message(RoleStates.waiting_user_for_admin, IsSuperAdminFilter())
async def add_admin_process(message: Message, state: FSMContext):
    target_id = await parse_user_input(message)
    if not target_id:
        return

    user = await get_user(target_id)
    if not user:
        user = await get_or_create_user(target_id)

    if user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        await message.answer(ALREADY_ADMIN.format(name=user.first_name or str(user.id)))
        await state.clear()
        return

    await update_user_role(user.id, UserRole.ADMIN)
    await message.answer(
        ADMIN_ADDED.format(
            name=user.first_name or str(user.id),
            user_id=user.id,
        )
    )
    await state.clear()


# ─── Remove Admin ────────────────────────────────────────────

@router.callback_query(F.data == "remove_admin_start", IsSuperAdminFilter())
async def remove_admin_start(callback: CallbackQuery, state: FSMContext):
    admins = await get_users_by_role(UserRole.ADMIN)
    if not admins:
        await callback.message.edit_text(
            "Нет администраторов для удаления.",
            reply_markup=back_kb("admin_roles")
        )
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for a in admins:
        name = a.first_name or str(a.id)
        builder.button(text=f"{name} (@{a.username or '—'})", callback_data=f"remove_admin_confirm:{a.id}")
    builder.button(text="🔙 Отмена", callback_data="admin_roles")
    builder.adjust(1)

    await callback.message.edit_text(
        "👑 <b>Выберите администратора для удаления:</b>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_admin_confirm:"), IsSuperAdminFilter())
async def remove_admin_confirm(callback: CallbackQuery):
    target_id = int(callback.data.split(":")[1])
    if target_id == callback.from_user.id:
        await callback.answer(CANT_REMOVE_SELF, show_alert=True)
        return

    if target_id in config.admin_ids:
        await callback.answer("❌ Нельзя удалить супер-администратора!", show_alert=True)
        return

    user = await get_user(target_id)
    if not user or user.role != UserRole.ADMIN:
        await callback.answer(NOT_ADMIN, show_alert=True)
        return

    await update_user_role(target_id, UserRole.USER)
    await callback.message.edit_text(
        ADMIN_REMOVED.format(
            name=user.first_name or str(user.id),
            user_id=user.id,
        ),
        reply_markup=back_kb("admin_roles")
    )
    await callback.answer()


# ─── List Group Moderators ──────────────────────────────────

@router.callback_query(F.data == "list_mods", IsAdminFilter())
async def list_mods(callback: CallbackQuery):
    async with get_session() as session:
        result = await session.execute(
            select(GroupModerator).order_by(GroupModerator.chat_id)
        )
        mods = list(result.scalars().all())

    if not mods:
        await callback.message.edit_text(NO_MODS, reply_markup=back_kb("admin_roles"))
        await callback.answer()
        return

    lines = [MOD_LIST_HEADER]
    for m in mods:
        user = await get_user(m.user_id)
        name = user.first_name if user else str(m.user_id)
        chat = await get_chat_name(m.chat_id)
        lines.append(
            MOD_LIST_ITEM.format(
                name=name,
                username=user.username if user else "—",
                user_id=m.user_id,
                chat=chat,
                perms=f"{'🔇' if m.can_mute else ''}{'🚫' if m.can_ban else ''}{'⚠️' if m.can_warn else ''}"
            )
        )
    await callback.message.edit_text("\n".join(lines), reply_markup=back_kb("admin_roles"))
    await callback.answer()


async def get_chat_name(chat_id: int) -> str:
    from bot.database.requests import get_chat
    chat = await get_chat(chat_id)
    return chat.title if chat else f"Чат {chat_id}"


# ─── Add Group Moderator ─────────────────────────────────────

@router.callback_query(F.data == "add_mod_start", IsAdminFilter())
async def add_mod_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🛡️ <b>Добавление модератора в группу</b>\n\n"
        "Отправьте ID пользователя, ID чата и через пробел.\n"
        "Пример: <code>123456789 -100987654321</code>\n\n"
        "Модератор получит права: mute, ban, warn, kick, delete.",
        reply_markup=back_kb("admin_roles")
    )
    await state.set_state(RoleStates.waiting_user_for_mod)
    await callback.answer()


@router.message(RoleStates.waiting_user_for_mod, IsAdminFilter())
async def add_mod_process(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Введите ID пользователя и ID чата через пробел.")
        return

    try:
        target_id = int(parts[0].lstrip("@"))
        chat_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректные ID. Введите два числа через пробел.")
        return

    user = await get_or_create_user(target_id)
    await add_group_moderator(
        user_id=target_id,
        chat_id=chat_id,
        created_by=message.from_user.id,
    )
    await message.answer(
        MOD_ADDED.format(
            name=user.first_name or str(user.id),
            chat_id=chat_id,
        )
    )
    await state.clear()


# ─── Remove Group Moderator ──────────────────────────────────

@router.callback_query(F.data == "remove_mod_start", IsAdminFilter())
async def remove_mod_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🛡️ <b>Удаление модератора</b>\n\n"
        "Отправьте ID пользователя и ID чата через пробел.\n"
        "Пример: <code>123456789 -100987654321</code>",
        reply_markup=back_kb("admin_roles")
    )
    await state.set_state(RoleStates.waiting_user_remove_mod)
    await callback.answer()


@router.message(RoleStates.waiting_user_remove_mod, IsAdminFilter())
async def remove_mod_process(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Введите ID пользователя и ID чата через пробел.")
        return

    try:
        target_id = int(parts[0].lstrip("@"))
        chat_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректные ID. Введите два числа через пробел.")
        return

    removed = await remove_group_moderator(target_id, chat_id)
    if removed:
        await message.answer(
            MOD_REMOVED.format(user_id=target_id, chat_id=chat_id)
        )
    else:
        await message.answer(NOT_MOD)
    await state.clear()


# ─── In-Group Commands (for chat admins) ────────────────────

@router.message(Command("mod"), IsGroupFilter())
async def cmd_mod(message: Message):
    if not await check_sender_is_group_owner_or_admin(message):
        return await message.answer("❌ Только владелец группы или админ бота может назначать модераторов.")

    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя, чтобы сделать его модератором.")

    await add_group_moderator(
        user_id=target.id,
        chat_id=message.chat.id,
        created_by=message.from_user.id,
    )
    await message.answer(
        f"✅ {target.full_name} назначен модератором группы!"
    )


@router.message(Command("unmod"), IsGroupFilter())
async def cmd_unmod(message: Message):
    if not await check_sender_is_group_owner_or_admin(message):
        return await message.answer("❌ Только владелец группы или админ бота может снимать модераторов.")

    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.answer("Ответьте на сообщение пользователя.")

    removed = await remove_group_moderator(target.id, message.chat.id)
    if removed:
        await message.answer(f"✅ {target.full_name} снят с должности модератора.")
    else:
        await message.answer("❌ Этот пользователь не является модератором.")


@router.message(Command("mods"), IsGroupFilter())
async def cmd_mods(message: Message):
    mods = await get_group_moderators(message.chat.id)
    if not mods:
        await message.answer("📭 В этой группе нет модераторов бота.")
        return

    lines = [f"<b>🛡️ Модераторы группы {message.chat.title}:</b>\n"]
    for m in mods:
        user = await get_user(m.user_id)
        name = user.first_name if user else str(m.user_id)
        lines.append(f"• {name} (@{user.username or '—'})")
    await message.answer("\n".join(lines))


async def check_sender_is_group_owner_or_admin(message: Message) -> bool:
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user and user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        return True
    member = await message.chat.get_member(user_id)
    return member.status in ("administrator", "creator")


async def parse_user_input(message: Message) -> int | None:
    text = message.text.strip()
    if text.startswith("@"):
        username = text[1:]
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()
            if user:
                return user.id
        await message.answer(f"❌ Пользователь @{username} не найден в базе.")
        return None
    try:
        return int(text)
    except ValueError:
        await message.answer("❌ Введите корректный ID или @username.")
        return None
