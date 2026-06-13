from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.requests import get_balance, confirm_and_topup
from bot.keyboards.inline import back_kb
from bot.loader import config

router = Router()

STAR_PRICES = {
    50: 1.0,
    100: 2.0,
    250: 5.0,
    500: 10.0,
    1000: 20.0,
    2500: 50.0,
}


@router.message(Command("buy"))
async def cmd_buy(message: Message):
    builder = InlineKeyboardBuilder()
    for stars, rub in STAR_PRICES.items():
        builder.button(
            text=f"⭐ {stars} звёзд = {rub:.0f}₽ на баланс",
            callback_data=f"buy_stars:{stars}"
        )
    builder.button(text="🔙 Отмена", callback_data="start")
    builder.adjust(1)

    await message.answer(
        "💰 <b>Пополнение баланса</b>\n\n"
        "Выберите количество Telegram ⭐ Звёзд для покупки.\n\n"
        "Курс: <code>1 звезда = 2 копейки</code>\n\n"
        "💳 Оплата через Telegram Stars.",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("buy_stars:"))
async def buy_stars(callback: CallbackQuery):
    stars = int(callback.data.split(":")[1])
    rub = STAR_PRICES[stars]

    prices = [LabeledPrice(label=f"⭐ {stars} звёзд", amount=stars)]

    await callback.message.answer_invoice(
        title=f"⭐ {stars} Telegram Stars",
        description=f"Пополнение баланса на {rub:.0f}₽",
        provider_token="",  # пустой для Stars
        currency="XTR",
        prices=prices,
        payload=f"topup:{stars}:{rub}",
        start_parameter="buy_stars",
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload

    if payload.startswith("topup:"):
        _, stars_str, rub_str = payload.split(":")
        stars = int(stars_str)
        rub = float(rub_str)

        await confirm_and_topup(
            user_id=message.from_user.id,
            rub_amount=rub,
            charge_id=payment.telegram_payment_charge_id,
            stars_amount=stars,
        )

        balance = await get_balance(message.from_user.id)
        await message.answer(
            f"✅ <b>Баланс пополнен!</b>\n\n"
            f"⭐ {stars} звёзд → +{rub:.0f}₽\n"
            f"💰 Текущий баланс: {balance:.2f}₽\n\n"
            f"Теперь вы можете купить рекламу через меню!"
        )


@router.message(Command("balance"))
async def cmd_balance(message: Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"💰 <b>Ваш баланс</b>\n\n"
        f"Баланс: <code>{balance:.2f}₽</code>\n\n"
        f"/buy — пополнить через ⭐ Stars",
        reply_markup=back_kb("start")
    )
