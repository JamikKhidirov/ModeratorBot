from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.database.requests import get_user
from bot.database.models import UserRole


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        user = await get_user(user_id)
        return user is not None and user.role in (UserRole.ADMIN, UserRole.SUPERADMIN)


class IsSuperAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        user = await get_user(user_id)
        return user is not None and user.role == UserRole.SUPERADMIN


class IsModeratorFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        user = await get_user(user_id)
        return user is not None and user.role in (UserRole.MODERATOR, UserRole.ADMIN, UserRole.SUPERADMIN)
