from functools import wraps
from aiogram.types import Message, CallbackQuery
from bot.database.models import UserRole


def admin_required(handler):
    @wraps(handler)
    async def wrapper(event: Message | CallbackQuery, *args, **kwargs):
        db_user = kwargs.get("db_user")
        if db_user and db_user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
            return await handler(event, *args, **kwargs)
        if isinstance(event, Message):
            await event.answer("❌ У вас нет прав администратора")
        elif isinstance(event, CallbackQuery):
            await event.answer("❌ Нет доступа", show_alert=True)
        return None
    return wrapper


def moderator_required(handler):
    @wraps(handler)
    async def wrapper(event: Message | CallbackQuery, *args, **kwargs):
        db_user = kwargs.get("db_user")
        if db_user and db_user.role in (UserRole.MODERATOR, UserRole.ADMIN, UserRole.SUPERADMIN):
            return await handler(event, *args, **kwargs)
        if isinstance(event, Message):
            await event.answer("❌ У вас нет прав модератора")
        elif isinstance(event, CallbackQuery):
            await event.answer("❌ Нет доступа", show_alert=True)
        return None
    return wrapper
