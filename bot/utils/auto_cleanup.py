from datetime import datetime, timezone, timedelta

from bot.database.requests import schedule_auto_delete, get_chat_settings


async def register_for_auto_delete(
    chat_id: int,
    message_id: int,
    override_hours: int = None,
):
    settings = await get_chat_settings(chat_id)
    hours = override_hours or (settings.auto_delete_time if settings else 0)
    if hours <= 0:
        return

    delete_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    await schedule_auto_delete(chat_id, message_id, delete_at)
