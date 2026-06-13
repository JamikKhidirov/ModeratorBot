from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.base import get_session
from bot.database.requests import (
    create_advertisement, get_user_ads, get_or_create_chat, add_balance,
)
from bot.database.models import Chat, AdStatus
from bot.keyboards.inline import back_kb
from bot.utils.texts import BUY_AD_TEXT, MY_ADS_HEADER, MY_AD_ITEM, NO_USER_ADS_TEXT

router = Router()


class AdCreation(StatesGroup):
    choosing_chat = State()
    entering_text = State()
    entering_price = State()


@router.callback_query(F.data == "buy_ad")
async def buy_ad_start(callback: CallbackQuery, state: FSMContext):
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Chat).limit(50))
        chats = list(result.scalars().all())

    if not chats:
        await callback.message.edit_text(
            "❌ Нет доступных чатов для размещения рекламы.",
            reply_markup=back_kb("start")
        )
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for chat in chats:
        name = chat.title or f"Чат {chat.id} ({chat.type})"
        builder.button(text=name, callback_data=f"ad_chat:{chat.id}")
    builder.button(text="🔙 Отмена", callback_data="start")
    builder.adjust(1)

    await callback.message.edit_text("📢 <b>Выберите чат для размещения рекламы:</b>", reply_markup=builder.as_markup())
    await callback.answer()
    await state.set_state(AdCreation.choosing_chat)


@router.callback_query(F.data.startswith("ad_chat:"), AdCreation.choosing_chat)
async def ad_chat_selected(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        BUY_AD_TEXT,
        reply_markup=back_kb("start")
    )
    await callback.answer()
    await state.set_state(AdCreation.entering_text)


@router.message(AdCreation.entering_text)
async def ad_text_received(message: Message, state: FSMContext):
    text = message.text or message.caption
    if not text or len(text) > 4000:
        await message.answer("❌ Текст слишком длинный (макс. 4000 символов). Попробуйте снова:")
        return

    media = None
    media_type = None
    if message.photo:
        media = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media = message.video.file_id
        media_type = "video"

    await state.update_data(text=text, media=media, media_type=media_type)
    await message.answer(
        "💰 <b>Укажите цену за размещение (в рублях):</b>\n\n"
        "Например: <code>100</code>",
        reply_markup=back_kb("start"),
    )
    await state.set_state(AdCreation.entering_price)


@router.message(AdCreation.entering_price)
async def ad_price_received(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ Укажите корректную цену (положительное число):")
        return

    data = await state.get_data()
    ad = await create_advertisement(
        user_id=message.from_user.id,
        chat_id=data["chat_id"],
        text=data["text"],
        price=price,
        media=data.get("media"),
        media_type=data.get("media_type"),
    )

    await message.answer(
        f"✅ <b>Заявка на рекламу #{ad.id} создана!</b>\n\n"
        f"Статус: ⏳ Ожидает одобрения администратора\n"
        f"Цена: {price:.2f} ₽\n\n"
        f"Как только администратор одобрит заявку, реклама будет опубликована.",
        reply_markup=back_kb("start"),
    )
    await state.clear()


@router.callback_query(F.data == "my_ads")
@router.message(F.text == "💰 Реклама")
async def my_ads(event: Message | CallbackQuery, db_user):
    ads = await get_user_ads(db_user.id)

    if not ads:
        text = NO_USER_ADS_TEXT
    else:
        lines = [MY_ADS_HEADER]
        for ad in ads:
            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌", "active": "📢", "completed": "✔️", "cancelled": "🚫"}
            emoji = status_emoji.get(ad.status.value, "❓")
            lines.append(
                f"{emoji} <b>#{ad.id}</b> | {ad.price}₽ | {emoji}{ad.status.value}\n"
                f"{ad.text[:50]}...\n"
            )
        text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=back_kb("start"))
        await event.answer()
    else:
        await event.answer(text, reply_markup=back_kb("start"))
