import logging
from aiogram import Router
from aiogram.types import ErrorEvent

router = Router()


@router.errors()
async def global_error_handler(event: ErrorEvent):
    logging.error(f"Global error: {event.exception}", exc_info=True)
    try:
        if event.update.message:
            await event.update.message.answer("❌ Произошла внутренняя ошибка. Попробуйте позже.")
        elif event.update.callback_query:
            await event.update.callback_query.answer("❌ Ошибка", show_alert=True)
    except Exception:
        pass
