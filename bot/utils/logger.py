from datetime import datetime, timezone

from bot.loader import bot
from bot.database.requests import get_chat


async def log_action(
    chat_id: int,
    action: str,
    moderator_name: str,
    target_name: str = None,
    reason: str = None,
    duration: str = None,
    extra: str = None,
):
    chat = await get_chat(chat_id)
    if not chat or not chat.log_chat_id:
        return

    log_chat_id = chat.log_chat_id
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"<b>📝 Действие:</b> {action}"]
    lines.append(f"<b>💬 Чат:</b> {chat.title or chat_id}")
    lines.append(f"<b>🕐 Время:</b> {time_str} UTC")
    lines.append(f"<b>👮 Модератор:</b> {moderator_name}")
    if target_name:
        lines.append(f"<b>👤 Цель:</b> {target_name}")
    if reason:
        lines.append(f"<b>📄 Причина:</b> {reason}")
    if duration:
        lines.append(f"<b>⏱ Длительность:</b> {duration}")
    if extra:
        lines.append(f"<b>📎 Дополнительно:</b> {extra}")

    try:
        await bot.send_message(log_chat_id, "\n".join(lines))
    except Exception:
        pass
