from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.requests import (
    add_chat_admin, remove_chat_admin, get_all_chat_admins,
    get_user, get_or_create_user, get_chat, get_user_chat_ids,
)
from bot.database.models import ChatAdmin
from bot.filters.admin import IsSuperAdminFilter
from bot.filters.chat_type import IsPrivateFilter
from bot.keyboards.inline import back_kb
from bot.utils.texts import (
    CHAT_ADMIN_ADDED, CHAT_ADMIN_REMOVED, CHAT_ADMIN_LIST_HEADER,
    CHAT_ADMIN_LIST_ITEM, NO_CHAT_ADMINS, CHAT_ADMIN_HELP,
)

router = Router()


class ChatAdminStates(StatesGroup):
    waiting_setadmin = State()
    waiting_removeadmin = State()


@router.message(Command("setadmin"), IsSuperAdminFilter(), IsPrivateFilter())
async def cmd_setadmin_start(message: Message, state: FSMContext):
    await message.answer(
        CHAT_ADMIN_HELP,
        reply_markup=back_kb("admin_roles"),
    )
    await state.set_state(ChatAdminStates.waiting_setadmin)


@router.message(ChatAdminStates.waiting_setadmin, IsSuperAdminFilter())
async def cmd_setadmin_process(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Введите ID пользователя и ID чата(ов) через пробел.\nПример: <code>123456789 -1001234567890</code>")
        return

    try:
        target_id = int(parts[0].lstrip("@"))
        chat_ids = []
        for p in parts[1:]:
            chat_ids.append(int(p))
    except ValueError:
        await message.answer("❌ Некорректные ID. Проверьте ввод.")
        return

    user = await get_or_create_user(target_id)
    added = []
    exists = []
    for chat_id in chat_ids:
        chat = await get_chat(chat_id)
        if not chat:
            await message.answer(f"❌ Чат {chat_id} не найден в базе.")
            continue
        result = await add_chat_admin(target_id, chat_id, message.from_user.id)
        if result:
            added.append(chat_id)
        else:
            exists.append(chat_id)

    lines = [f"✅ <b>Администратор чатов назначен!</b>\n👤 {user.first_name or user.id} (ID: <code>{user.id}</code>)\n"]
    if added:
        lines.append(f"➕ Добавлено чатов: <code>{len(added)}</code>")
    if exists:
        lines.append(f"ℹ️ Уже были админом в: <code>{len(exists)}</code>")
    await message.answer("\n".join(lines))
    await state.clear()


@router.message(Command("removeadmin"), IsSuperAdminFilter(), IsPrivateFilter())
async def cmd_removeadmin_start(message: Message, state: FSMContext):
    await message.answer(
        "🗑 <b>Удаление администратора чата</b>\n\n"
        "Отправьте ID пользователя и ID чата через пробел.\n"
        "Пример: <code>123456789 -1001234567890</code>",
        reply_markup=back_kb("admin_roles"),
    )
    await state.set_state(ChatAdminStates.waiting_removeadmin)


@router.message(ChatAdminStates.waiting_removeadmin, IsSuperAdminFilter())
async def cmd_removeadmin_process(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Введите ID пользователя и ID чата через пробел.")
        return

    try:
        target_id = int(parts[0].lstrip("@"))
        chat_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректные ID.")
        return

    removed = await remove_chat_admin(target_id, chat_id)
    if removed:
        await message.answer(
            CHAT_ADMIN_REMOVED.format(user_id=target_id, chat_id=chat_id)
        )
    else:
        await message.answer("❌ Этот пользователь не является администратором данного чата.")
    await state.clear()


@router.message(Command("chatadmins"), IsSuperAdminFilter(), IsPrivateFilter())
async def cmd_chatadmins(message: Message):
    admins = await get_all_chat_admins()
    if not admins:
        await message.answer(NO_CHAT_ADMINS, reply_markup=back_kb("admin_roles"))
        return

    from collections import defaultdict
    by_user = defaultdict(list)
    for a in admins:
        by_user[a.user_id].append(a.chat_id)

    lines = [CHAT_ADMIN_LIST_HEADER]
    for user_id, chat_ids in by_user.items():
        user = await get_user(user_id)
        name = user.first_name if user else str(user_id)
        lines.append(
            CHAT_ADMIN_LIST_ITEM.format(
                name=name,
                username=user.username if user else "—",
                user_id=user_id,
                chats=", ".join(str(c) for c in chat_ids[:5]),
                total=len(chat_ids),
            )
        )
    await message.answer("\n".join(lines), reply_markup=back_kb("admin_roles"))
