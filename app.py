import asyncio
import logging

from bot.loader import bot, dp, config
from bot.database.base import init_db, close_db
from bot.handlers import register_handlers
from bot.middlewares.throttle import ThrottlingMiddleware
from bot.middlewares.acl import ACLMiddleware
from bot.handlers.advertising.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup():
    if not config.bot_token or config.bot_token == "YOUR_BOT_TOKEN_HERE":
        print("╔═══════════════════════════════════════════════╗")
        print("║  ❌ ОШИБКА: Токен бота не указан!           ║")
        print("║                                             ║")
        print("║  Открой файл .env и вставь свой токен:      ║")
        print("║  BOT_TOKEN=1234567890:ABCdef...              ║")
        print("║                                             ║")
        print("║  Получить токен: @BotFather                  ║")
        print("╚═══════════════════════════════════════════════╝")
        return

    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова")

    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    dp.message.middleware(ACLMiddleware())
    dp.callback_query.middleware(ACLMiddleware())

    register_handlers()

    await start_scheduler()
    logger.info("Планировщик рекламы запущен")

    if config.admin_ids:
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(admin_id, "✅ <b>Бот запущен и готов к работе!</b>")
            except Exception:
                pass

    logger.info(f"Бот запущен! @{(await bot.me()).username}")


async def on_shutdown():
    logger.info("Остановка бота...")
    await close_db()
    await bot.session.close()


async def main():
    await on_startup()
    try:
        await dp.start_polling(
            bot,
            skip_updates=config.skip_updates,
            allowed_updates=["message", "callback_query", "my_chat_member", "chat_member"],
        )
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
