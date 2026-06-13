import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_

from bot.database.base import get_session
from bot.database.requests import (
    get_ready_ads, get_pending_scheduled, mark_scheduled_sent,
    get_recurring_posts, get_active_rss_feeds, update_rss_feed,
    get_expired_messages, delete_auto_message_record,
    get_expired_giveaways, get_giveaway_participants, complete_giveaway,
)
from bot.database.models import AdStatus, Punishment, PunishmentType, Chat
from bot.loader import bot


async def process_advertisements():
    while True:
        try:
            ads = await get_ready_ads()
            for ad in ads:
                try:
                    chat_id = ad.chat_id
                    if ad.media and ad.media_type == "photo":
                        await bot.send_photo(chat_id, ad.media, caption=ad.text)
                    elif ad.media and ad.media_type == "video":
                        await bot.send_video(chat_id, ad.media, caption=ad.text)
                    else:
                        await bot.send_message(chat_id, ad.text)

                    ad.times_posted += 1
                    if ad.times_posted >= ad.max_posts:
                        ad.status = AdStatus.COMPLETED

                    async with get_session() as session:
                        session.add(ad)
                        await session.commit()

                except Exception as e:
                    logging.error(f"Ad posting error #{ad.id}: {e}")
        except Exception as e:
            logging.error(f"Ad scheduler error: {e}")
        await asyncio.sleep(60)


async def process_scheduled_messages():
    while True:
        try:
            msgs = await get_pending_scheduled()
            for msg in msgs:
                try:
                    if msg.media and msg.media_type == "photo":
                        await bot.send_photo(msg.chat_id, msg.media, caption=msg.text)
                    elif msg.media and msg.media_type == "video":
                        await bot.send_video(msg.chat_id, msg.media, caption=msg.text)
                    else:
                        await bot.send_message(msg.chat_id, msg.text or "⏰")
                    await mark_scheduled_sent(msg.id)
                except Exception as e:
                    logging.error(f"Scheduled msg #{msg.id}: {e}")
        except Exception as e:
            logging.error(f"Scheduled msg error: {e}")
        await asyncio.sleep(30)


async def auto_unmute_checker():
    while True:
        try:
            now = datetime.now(timezone.utc)
            async with get_session() as session:
                result = await session.execute(
                    select(Punishment).where(
                        and_(
                            Punishment.type == PunishmentType.MUTE,
                            Punishment.active.is_(True),
                            Punishment.expires_at.is_not(None),
                            Punishment.expires_at <= now,
                        )
                    )
                )
                expired = list(result.scalars().all())
                for p in expired:
                    try:
                        await bot.restrict_chat_member(
                            p.chat_id, p.user_id,
                            permissions=type("P", (), {"can_send_messages": True})(),
                        )
                        p.active = False
                        session.add(p)
                    except Exception:
                        pass
                if expired:
                    await session.commit()
        except Exception as e:
            logging.error(f"Auto-unmute error: {e}")
        await asyncio.sleep(30)


async def recurring_posts_dispatcher():
    while True:
        try:
            posts = await get_recurring_posts()
            now = datetime.now(timezone.utc)
            for post in posts:
                try:
                    match = False
                    if post.day_of_week is not None:
                        if now.weekday() == post.day_of_week and now.hour == post.hour and now.minute == post.minute:
                            match = True
                    elif post.interval_days:
                        if now.hour == post.hour and now.minute == post.minute:
                            minutes_since_midnight = now.hour * 60 + now.minute
                            if minutes_since_midnight == post.hour * 60 + post.minute:
                                match = True

                    if match:
                        if post.media and post.media_type == "photo":
                            await bot.send_photo(post.chat_id, post.media, caption=post.text)
                        elif post.media and post.media_type == "video":
                            await bot.send_video(post.chat_id, post.media, caption=post.text)
                        else:
                            await bot.send_message(post.chat_id, post.text or "⏰")
                except Exception as e:
                    logging.error(f"Recurring post #{post.id}: {e}")
        except Exception as e:
            logging.error(f"Recurring error: {e}")
        await asyncio.sleep(30)


async def rss_poller():
    while True:
        try:
            feeds = await get_active_rss_feeds()
            now = datetime.now(timezone.utc)
            for feed in feeds:
                try:
                    if feed.last_fetched:
                        elapsed = (now - feed.last_fetched).total_seconds() / 60
                        if elapsed < feed.interval_minutes:
                            continue

                    import urllib.request
                    import xml.etree.ElementTree as ET

                    req = urllib.request.Request(feed.url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = resp.read()

                    root = ET.fromstring(data)
                    channel = root.find("channel")
                    if channel is None:
                        channel = root

                    items = channel.findall("item")
                    new_items = []
                    for item in items[:3]:
                        guid = item.findtext("guid") or item.findtext("link") or ""
                        if guid and guid != feed.last_guid:
                            new_items.append(item)

                    if new_items:
                        feed.last_guid = new_items[0].findtext("guid") or new_items[0].findtext("link") or ""
                        feed.last_fetched = now
                        async with get_session() as session:
                            session.add(feed)
                            await session.commit()

                        for item in reversed(new_items):
                            title = item.findtext("title", "Новость")
                            link = item.findtext("link", "")
                            desc = item.findtext("description", "")[:200]
                            text = f"<b>{title}</b>\n\n{desc}\n\n<a href='{link}'>Читать дальше</a>"
                            try:
                                await bot.send_message(feed.chat_id, text, disable_web_page_preview=True)
                            except Exception:
                                pass
                    else:
                        feed.last_fetched = now
                        async with get_session() as session:
                            session.add(feed)
                            await session.commit()

                except Exception as e:
                    logging.error(f"RSS feed #{feed.id} ({feed.url}): {e}")
        except Exception as e:
            logging.error(f"RSS poller error: {e}")
        await asyncio.sleep(120)


async def auto_delete_checker():
    while True:
        try:
            msgs = await get_expired_messages()
            for m in msgs:
                try:
                    await bot.delete_message(m.chat_id, m.message_id)
                except Exception:
                    pass
                await delete_auto_message_record(m.id)
        except Exception as e:
            logging.error(f"Auto-delete error: {e}")
        await asyncio.sleep(30)


async def giveaway_winner_checker():
    while True:
        try:
            giveaways = await get_expired_giveaways()
            for g in giveaways:
                participants = await get_giveaway_participants(g.id)
                winner_mentions = []
                if participants:
                    import random
                    winners = random.sample(participants, min(g.winners_count, len(participants)))
                    for w in winners:
                        try:
                            await bot.send_message(
                                w.user_id,
                                f"🎉 <b>Поздравляем! Вы выиграли!</b>\n\n"
                                f"🎁 Розыгрыш: {g.title}\n"
                                f"🏆 Приз: {g.prize}\n\n"
                                f"Свяжитесь с администратором для получения приза.",
                            )
                        except Exception:
                            pass
                        winner_mentions.append(f"<a href=\"tg://user?id={w.user_id}\">{w.user_id}</a>")

                try:
                    new_text = (
                        f"🎁 <b>Розыгрыш завершён</b>\n\n"
                        f"📌 {g.title}\n"
                        f"🎁 {g.prize}\n"
                    )
                    if winner_mentions:
                        new_text += f"\n🏆 <b>Победители:</b>\n" + "\n".join(f"• {m}" for m in winner_mentions)
                        new_text += "\n\nПоздравляем!"
                    else:
                        new_text += "\n😔 Нет участников."

                    await bot.edit_message_text(new_text, g.chat_id, g.message_id)
                except Exception:
                    pass

                await complete_giveaway(g.id)
        except Exception as e:
            logging.error(f"Giveaway winner checker: {e}")
        await asyncio.sleep(30)


async def start_scheduler():
    asyncio.create_task(process_advertisements())
    asyncio.create_task(process_scheduled_messages())
    asyncio.create_task(auto_unmute_checker())
    asyncio.create_task(recurring_posts_dispatcher())
    asyncio.create_task(rss_poller())
    asyncio.create_task(auto_delete_checker())
    asyncio.create_task(giveaway_winner_checker())
