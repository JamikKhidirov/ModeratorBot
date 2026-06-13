from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.requests import (
    create_advertisement, get_user_ads, get_chats_with_prices,
    get_balance, deduct_balance, get_chat, get_user,
)
from bot.database.models import Chat
from bot.keyboards.inline import back_kb
from bot.utils.texts import BUY_AD_TEXT, NO_USER_ADS_TEXT

router = Router()


class AdCreation(StatesGroup):
    choosing_chat = State()
    confirming = State()
    entering_text = State()


@router.callback_query(F.data == "buy_ad")
async def buy_ad_start(callback: CallbackQuery, state: FSMContext):
    chats = await get_chats_with_prices()
    if not chats:
        await callback.message.edit_text(
            "❌ Нет доступных чатов для рекламы. Администратор ещё не настроил цены.",
            reply_markup=back_kb("start")
        )
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for chat in chats:
        name = chat.title or f"Чат {chat.id}"
        builder.button(
            text=f"{name} — {chat.ad_price:.0f}⭐",
            callback_data=f"ad_chat:{chat.id}"
        )
    builder.button(text="🔙 Отмена", callback_data="start")
    builder.adjust(1)

    await callback.message.edit_text(
        "📢 <b>Покупка рекламы</b>\n\n"
        "Выберите чат для размещения. Цена указана в ⭐:\n"
        "После выбора с вас спишется сумма.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
    await state.set_state(AdCreation.choosing_chat)


@router.callback_query(F.data.startswith("ad_chat:"), AdCreation.choosing_chat)
async def ad_chat_selected(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    chat = await get_chat(chat_id)
    if not chat or chat.ad_price <= 0:
        await callback.answer("❌ Цена не установлена", show_alert=True)
        return

    balance = await get_balance(callback.from_user.id)
    price = chat.ad_price

    if balance < price:
        await callback.message.edit_text(
            f"❌ <b>Недостаточно средств!</b>\n\n"
            f"💰 Баланс: {balance:.2f}₽\n"
            f"💵 Требуется: {price:.0f}⭐\n"
            f"Вам не хватает: {price - balance:.2f}₽\n\n"
            f"Пополните баланс через /buy",
            reply_markup=back_kb("start")
        )
        await callback.answer()
        return

    await state.update_data(chat_id=chat_id, price=price, chat_title=chat.title)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="ad_confirm_pay")
    builder.button(text="🔙 Назад", callback_data="buy_ad")
    builder.adjust(1)

    await callback.message.edit_text(
        f"📢 <b>Реклама в {chat.title}</b>\n\n"
        f"💰 Цена: <code>{price:.0f}⭐</code>\n"
        f"💳 Ваш баланс: <code>{balance:.2f}₽</code>\n\n"
        f"После подтверждения с вас будет списано <code>{price:.0f}⭐</code>.\n\n"
        f"Теперь отправьте текст рекламного объявления\n"
        f"(можно с фото или видео):",
        reply_markup=back_kb("buy_ad")
    )
    await callback.answer()
    await state.set_state(AdCreation.entering_text)


@router.message(AdCreation.entering_text)
async def ad_text_received(message: Message, state: FSMContext):
    data = await state.get_data()
    text = message.text or message.caption
    if not text or len(text) > 4000:
        await message.answer("❌ Текст слишком длинный (макс. 4000 символов).")
        return

    media = None
    media_type = None
    if message.photo:
        media = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media = message.video.file_id
        media_type = "video"

    price = data["price"]
    ok = await deduct_balance(message.from_user.id, price)
    if not ok:
        await message.answer("❌ Недостаточно средств. Пополните через /buy")
        await state.clear()
        return

    ad = await create_advertisement(
        user_id=message.from_user.id,
        chat_id=data["chat_id"],
        text=text,
        price=price,
        media=media,
        media_type=media_type,
    )

    await message.answer(
        f"✅ <b>Реклама #{ad.id} оплачена и создана!</b>\n\n"
        f"💬 Чат: {data.get('chat_title', '—')}\n"
        f"💵 Сумма: <code>{price:.0f}⭐</code>\n"
        f"📊 Статус: ⏳ Ожидает одобрения администратора\n\n"
        f"Как только админ одобрит — реклама будет опубликована.",
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
        lines = ["<b>📋 Мои объявления</b>\n"]
        for ad in ads:
            emoji_map = {"pending": "⏳", "approved": "✅", "rejected": "❌", "active": "📢", "completed": "✔️", "cancelled": "🚫"}
            e = emoji_map.get(ad.status.value, "❓")
            lines.append(
                f"{e} <b>#{ad.id}</b> | {ad.price:.0f}⭐ | {e} {ad.status.value}\n"
                f"{(ad.text or '')[:50]}...\n"
            )
        text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=back_kb("start"))
        await event.answer()
    else:
        await event.answer(text, reply_markup=back_kb("start"))
