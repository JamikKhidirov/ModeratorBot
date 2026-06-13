from aiogram.filters import BaseFilter
from aiogram.types import Message


class IsGroupFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in ("group", "supergroup")


class IsPrivateFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type == "private"
