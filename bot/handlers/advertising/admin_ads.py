from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.database.base import get_session
from bot.database.requests import (
    get_pending_ads, update_ad_status, get_user, get_chat, add_balance,
    get_user_chat_ids, is_chat_admin_assigned,
)
from bot.database.models import Advertisement, AdStatus, UserRole
from bot.filters.admin import IsAdminFilter
from bot.keyboards.inline import ads_list_kb, ad_action_kb, back_kb
from bot.keyboards.reply import remove_kb
from bot.utils.texts import AD_VIEW_TEXT, NO_ADS_TEXT

router = Router()


async def _is_full_admin(user_id: int) -> bool:
    user = await get_user(user_id)
    return user is not None and user.role in (UserRole.ADMIN, UserRole.SUPERADMIN)


async def _get_visible_ads(user_id: int):
    if await _is_full_admin(user_id):
        return await get_pending_ads()
    chat_ids = await get_user_chat_ids(user_id)
    if not chat_ids:
        return []
    async with get_session() as session:
        result = await session.execute(
            select(Advertisement).where(
                Advertisement.status == AdStatus.PENDING,
                Advertisement.chat_id.in_(chat_ids),
            )
        )
        return list(result.scalars().all())


async def _can_manage_ad(user_id: int, ad: Advertisement) -> bool:
    if await _is_full_admin(user_id):
        return True
    return await is_chat_admin_assigned(user_id, ad.chat_id)


@router.callback_query(F.data == "admin_ads_list")
async def admin_ads_list(callback: CallbackQuery):
    if not await _is_full_admin(callback.from_user.id):
        chat_ids = await get_user_chat_ids(callback.from_user.id)
        if not chat_ids:
            await callback.answer("❌ Нет доступа", show_alert=True)
            return

    ads = await _get_visible_ads(callback.from_user.id)
    if not ads:
        await callback.message.edit_text(NO_ADS_TEXT, reply_markup=back_kb("admin_panel"))
        await callback.answer()
        return
    await callback.message.edit_text(
        "📢 <b>Заявки на рекламу:</b>",
        reply_markup=ads_list_kb(ads)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ad_view:"))
async def ad_view(callback: CallbackQuery):
    ad_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        result = await session.execute(
            select(Advertisement).where(Advertisement.id == ad_id)
        )
        ad = result.scalar_one_or_none()
    if not ad:
        await callback.answer("Объявление не найдено", show_alert=True)
        return

    if not await _can_manage_ad(callback.from_user.id, ad):
        await callback.answer("❌ Нет доступа к этому объявлению", show_alert=True)
        return

    user = await get_user(ad.user_id)
    chat = await get_chat(ad.chat_id)
    text = AD_VIEW_TEXT.format(
        ad_id=ad.id,
        user_id=ad.user_id,
        chat_title=chat.title if chat else f"Чат {ad.chat_id}",
        price=ad.price,
        status=ad.status.value,
        text=ad.text[:500],
    )
    await callback.message.edit_text(text, reply_markup=ad_action_kb(ad_id))
    await callback.answer()


@router.callback_query(F.data.startswith("ad_approve:"))
async def ad_approve(callback: CallbackQuery):
    ad_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        result = await session.execute(
            select(Advertisement).where(Advertisement.id == ad_id)
        )
        ad = result.scalar_one_or_none()
    if not ad:
        await callback.answer("Объявление не найдено", show_alert=True)
        return
    if not await _can_manage_ad(callback.from_user.id, ad):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await update_ad_status(ad_id, AdStatus.APPROVED)
    await callback.answer("✅ Реклама одобрена!", show_alert=True)
    await callback.message.edit_text(
        f"✅ Реклама #{ad_id} одобрена и будет опубликована.",
        reply_markup=back_kb("admin_ads_list")
    )


@router.callback_query(F.data.startswith("ad_reject:"))
async def ad_reject(callback: CallbackQuery):
    ad_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        result = await session.execute(
            select(Advertisement).where(Advertisement.id == ad_id)
        )
        ad = result.scalar_one_or_none()
    if not ad:
        await callback.answer("Объявление не найдено", show_alert=True)
        return
    if not await _can_manage_ad(callback.from_user.id, ad):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await update_ad_status(ad_id, AdStatus.REJECTED)
    await callback.answer("❌ Реклама отклонена", show_alert=True)
    await callback.message.edit_text(
        f"❌ Реклама #{ad_id} отклонена.",
        reply_markup=back_kb("admin_ads_list")
    )
