from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION

from bot.database.requests import get_or_create_chat, get_chat_settings
from bot.utils.texts import WELCOME_MESSAGE

router = Router()


@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def bot_added_to_group(event: ChatMemberUpdated):
    chat = event.chat
    await get_or_create_chat(
        chat_id=chat.id,
        title=chat.title,
        chat_type=chat.type,
        username=chat.username,
    )
    await event.bot.send_message(
        chat.id,
        f"👋 Привет! Я бот-модератор.\nИспользуйте /admin для настройки."
    )


@router.message(F.new_chat_members)
async def welcome_new_member(message: Message):
    chat = await get_or_create_chat(
        chat_id=message.chat.id,
        title=message.chat.title,
        chat_type=message.chat.type,
    )
    settings = await get_chat_settings(message.chat.id)

    for member in message.new_chat_members:
        if member.is_bot:
            continue

        if settings and settings.welcome_enabled:
            text = settings.welcome_message or WELCOME_MESSAGE
            await message.answer(
                text.format(
                    name=member.full_name,
                    chat_title=message.chat.title,
                )
            )
        elif not settings or not settings.welcome_message:
            await message.answer(
                WELCOME_MESSAGE.format(
                    name=member.full_name,
                    chat_title=message.chat.title,
                )
            )
