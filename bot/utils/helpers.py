from datetime import timedelta
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ChatType


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        return f"{seconds // 60} мин"
    elif seconds < 86400:
        return f"{seconds // 3600} ч"
    else:
        return f"{seconds // 86400} д"


def parse_duration(text: str) -> int | None:
    text = text.lower().strip()
    multipliers = {"с": 1, "сек": 1, "м": 60, "мин": 60, "ч": 3600, "д": 86400}
    try:
        if text.isdigit():
            return int(text) * 60
        for suffix, mult in multipliers.items():
            if text.endswith(suffix):
                num = text.rstrip(suffix).strip()
                if num.isdigit():
                    return int(num) * mult
    except (ValueError, TypeError):
        return None
    return None


def mention_user(message: Message) -> str:
    user = message.from_user
    if user.username:
        return f"@{user.username}"
    return f"<a href=\"tg://user?id={user.id}\">{user.full_name}</a>"


def is_group(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def is_admin_chat(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE
