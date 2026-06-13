from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import Advertisement, AdStatus


def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👑 Роли и админы", callback_data="admin_roles")
    builder.button(text="🚨 Жалобы", callback_data="admin_reports")
    builder.button(text="📢 Реклама (заявки)", callback_data="admin_ads_list")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="⚙️ Настройки чатов", callback_data="admin_settings")
    builder.adjust(2)
    return builder.as_markup()


def moderation_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Выдать варн", callback_data=f"warn:{user_id}")
    builder.button(text="Мут", callback_data=f"mute:{user_id}")
    builder.button(text="Бан", callback_data=f"ban:{user_id}")
    builder.button(text="Кик", callback_data=f"kick:{user_id}")
    builder.button(text="Снять все", callback_data=f"unpunish:{user_id}")
    builder.adjust(2)
    return builder.as_markup()


def mute_duration_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for text, secs in [("5 мин", 300), ("15 мин", 900), ("30 мин", 1800), ("1 час", 3600), ("6 часов", 21600), ("24 часа", 86400)]:
        builder.button(text=text, callback_data=f"mute_set:{user_id}:{secs}")
    builder.adjust(3)
    return builder.as_markup()


def ads_list_kb(ads: list[Advertisement], page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ad in ads:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌", "active": "📢", "completed": "✔️", "cancelled": "🚫"}
        emoji = status_emoji.get(ad.status.value, "❓")
        builder.button(
            text=f"{emoji} #{ad.id} | {ad.user_id} | {ad.price}₽",
            callback_data=f"ad_view:{ad.id}"
        )
    builder.adjust(1)
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"ads_page:{page - 1}")
    if len(ads) == 10:
        builder.button(text="➡️ Вперед", callback_data=f"ads_page:{page + 1}")
    builder.button(text="❌ Закрыть", callback_data="ads_close")
    return builder.as_markup()


def ad_action_kb(ad_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"ad_approve:{ad_id}")
    builder.button(text="❌ Отклонить", callback_data=f"ad_reject:{ad_id}")
    builder.button(text="🔙 Назад", callback_data="admin_ads_list")
    builder.adjust(2)
    return builder.as_markup()


def chat_settings_kb(chat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👋 Приветствие", callback_data=f"set_welcome:{chat_id}")
    builder.button(text="🔗 Ссылки (вкл/выкл)", callback_data=f"toggle_links:{chat_id}")
    builder.button(text="🤬 Мат (вкл/выкл)", callback_data=f"toggle_badwords:{chat_id}")
    builder.button(text="🔒 Капча", callback_data=f"toggle_captcha:{chat_id}")
    builder.button(text="⚠️ Макс. варнов", callback_data=f"set_maxwarns:{chat_id}")
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(2)
    return builder.as_markup()


def register_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Купить рекламу", callback_data="buy_ad")
    builder.button(text="📋 Мои объявления", callback_data="my_ads")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="❓ Помощь", callback_data="help")
    builder.adjust(2)
    return builder.as_markup()


def back_kb(callback: str = "admin_panel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=callback)
    return builder.as_markup()
