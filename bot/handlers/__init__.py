from bot.loader import dp

from bot.handlers.users.start import router as start_router
from bot.handlers.groups.moderation import router as moderation_router
from bot.handlers.groups.admin_commands import router as admin_commands_router
from bot.handlers.groups.admin_roles import router as admin_roles_router
from bot.handlers.groups.join_requests import router as join_requests_router
from bot.handlers.groups.auto_moderation import router as auto_moderation_router
from bot.handlers.groups.report import router as report_router
from bot.handlers.groups.captcha import router as captcha_router
from bot.handlers.groups.advanced_admin import router as advanced_admin_router
from bot.handlers.groups.stats import router as stats_router
from bot.handlers.groups.scheduled import router as scheduled_router
from bot.handlers.groups.recurring import router as recurring_router
from bot.handlers.groups.rss import router as rss_router
from bot.handlers.groups.welcome_editor import router as welcome_editor_router
from bot.handlers.payments import router as payments_router
from bot.handlers.advertising.buyer import router as buyer_router
from bot.handlers.advertising.admin_ads import router as admin_ads_router
from bot.handlers.errors.error_handler import router as error_router


def register_handlers():
    dp.include_router(start_router)
    dp.include_router(moderation_router)
    dp.include_router(admin_commands_router)
    dp.include_router(admin_roles_router)
    dp.include_router(join_requests_router)
    dp.include_router(auto_moderation_router)
    dp.include_router(report_router)
    dp.include_router(captcha_router)
    dp.include_router(advanced_admin_router)
    dp.include_router(stats_router)
    dp.include_router(scheduled_router)
    dp.include_router(recurring_router)
    dp.include_router(rss_router)
    dp.include_router(welcome_editor_router)
    dp.include_router(payments_router)
    dp.include_router(buyer_router)
    dp.include_router(admin_ads_router)
    dp.include_router(error_router)
