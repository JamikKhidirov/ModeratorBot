START_TEXT = """
👋 <b>Добро пожаловать в ModeratorBot!</b>

Я мощный бот для модерации чатов и управления рекламой.

<b>Основные возможности:</b>
🔨 Модерация: mute, ban, warn, kick, clear
📢 Реклама: покупка и публикация в каналах/чатах
⚙️ Гибкие настройки для каждого чата
🛡️ Защита от спама и нежелательного контента

<b>Команды:</b>
/start — Главное меню
/help — Помощь
/mute [время] — Замутить пользователя
/ban — Забанить пользователя
/warn [причина] — Выдать предупреждение
/unmute — Снять мут
/unban — Разбанить
/kick — Кикнуть пользователя
/clear [N] — Очистить сообщения
/admin — Панель администратора

<i>Добавьте меня в группу с правами администратора для начала работы!</i>
"""

HELP_TEXT = """
<b>❓ Помощь по ModeratorBot</b>

<b>Для пользователей:</b>
• Добавьте бота в чат с правами администратора
• Используйте /admin для настройки модерации
• Купить рекламу — кнопка "💰 Реклама"

<b>Для рекламодателей:</b>
1. Нажмите "💰 Реклама"
2. Выберите чат для размещения
3. Оплатите и отправьте текст
4. После одобрения админом реклама будет опубликована

<b>Команды модерации (в группах):</b>
/mute @user [время] — Мут
/ban @user — Бан
/kick @user — Кик
/warn @user [причина] — Варн
/unmute @user — Снять мут
/unban @user — Разбанить
/clear [N] — Удалить N сообщений

<i>По всем вопросам: @admin</i>
"""

PROFILE_TEXT = """
<b>👤 Ваш профиль</b>
ID: <code>{user_id}</code>
Имя: {first_name}
Username: @{username}
Роль: {role}
Баланс: {balance:.2f} ₽

<b>Статистика:</b>
Варнов: {warns}
Реклама: {ads_count} объявлений
"""

ADMIN_PANEL_TEXT = """
<b>⚙️ Панель администратора</b>

Выберите раздел:
• 📊 Статистика бота
• 📢 Управление рекламой
• 👥 Управление пользователями
• ⚙️ Настройки чатов
"""

ADMIN_STATS_TEXT = """
<b>📊 Статистика бота</b>

👥 Пользователей: {users}
💬 Чатов: {chats}
📢 Реклама: {ads_total} всего
⏳ Ожидают: {ads_pending}
✅ Одобрено: {ads_approved}
❌ Отклонено: {ads_rejected}
💰 Доход: {total_revenue:.2f} ₽
"""

NO_ADS_TEXT = "📭 Нет заявок на рекламу."
NO_USER_ADS_TEXT = "📭 У вас нет рекламных объявлений."

BUY_AD_TEXT = """
<b>💰 Покупка рекламы</b>

Отправьте текст рекламного объявления.
Вы также можете добавить фото или видео к сообщению.

<i>Цена рекламы зависит от чата. После отправки текста админ рассмотрит вашу заявку.</i>
"""

MY_ADS_HEADER = "<b>📋 Мои объявления</b>\n\n"
MY_AD_ITEM = "#{id} | Статус: {status} | Цена: {price}₽ | Просмотров: {views}/{goal if goal else '∞'}\n"

AD_VIEW_TEXT = """
<b>📢 Объявление #{ad_id}</b>

👤 Пользователь: <a href="tg://user?id={user_id}">{user_id}</a>
💬 Чат: {chat_title}
💰 Цена: {price} ₽
📊 Статус: {status}
📝 Текст:
{text}
"""

MUTE_SUCCESS = "✅ Пользователь <a href=\"tg://user?id={user_id}\">{name}</a> замучен на {duration}"
UNMUTE_SUCCESS = "✅ Пользователь <a href=\"tg://user?id={user_id}\">{name}</a> размучен"
BAN_SUCCESS = "✅ Пользователь <a href=\"tg://user?id={user_id}\">{name}</a> забанен"
UNBAN_SUCCESS = "✅ Пользователь <a href=\"tg://user?id={user_id}\">{name}</a> разбанен"
KICK_SUCCESS = "✅ Пользователь <a href=\"tg://user?id={user_id}\">{name}</a> кикнут"
WARN_SUCCESS = "⚠️ Пользователь <a href=\"tg://user?id={user_id}\">{name}</a> получил варн ({count}/{max})\nПричина: {reason}"
WARN_BAN = "🚫 Пользователь <a href=\"tg://user?id={user_id}\">{name}</a> забанен (превышен лимит варнов)"
CLEAR_SUCCESS = "✅ Удалено {count} сообщений"
NO_RIGHTS = "❌ У бота недостаточно прав для выполнения этого действия!"
USER_NOT_FOUND = "❌ Пользователь не найден"
CHAT_NOT_CONFIGURED = "⚙️ Настройте бота через /admin в группе"

WELCOME_MESSAGE = """
👋 Добро пожаловать, {name}!

Добро пожаловать в {chat_title}!

<i>Пожалуйста, соблюдайте правила чата.</i>
"""

WARN_LIST_TEXT = "<b>⚠️ Список варнов пользователя</b>\n\n"
WARN_ITEM = "• {reason or 'Без причины'} — {date}\n"

NOWARN_TEXT = "✅ У пользователя нет активных варнов"
CLEAR_WARNS = "✅ Варны пользователя очищены"

# ─── Admin Role Management ──────────────────────────────────

ADMIN_LIST_HEADER = "<b>👑 Список администраторов:</b>\n\n"
ADMIN_LIST_ITEM = "{emoji} <b>{name}</b>\n   └ @{username} | ID: <code>{user_id}</code> | Роль: {role} {super_emoji}\n"
NO_ADMINS = "📭 Нет администраторов."

MOD_LIST_HEADER = "<b>🛡️ Список модераторов групп:</b>\n\n"
MOD_LIST_ITEM = "🛡️ <b>{name}</b>\n   └ @{username} | ID: <code>{user_id}</code>\n   └ Группа: {chat}\n   └ Права: {perms}\n"
NO_MODS = "📭 Нет модераторов."

ADMIN_ADDED = "✅ <b>Администратор добавлен!</b>\n\n👤 {name} (ID: <code>{user_id}</code>)\nТеперь у пользователя есть доступ к /admin"
ADMIN_REMOVED = "❌ <b>Администратор удалён</b>\n\n👤 {name} (ID: <code>{user_id}</code>)\nПрава администратора отозваны."

MOD_ADDED = "✅ <b>Модератор добавлен!</b>\n\n👤 {name}\n💬 Чат: <code>{chat_id}</code>"
MOD_REMOVED = "❌ Модератор удалён.\n👤 ID: <code>{user_id}</code>\n💬 Чат: <code>{chat_id}</code>"

# ─── Giveaway ───────────────────────────────────────────────

GIVEAWAY_CREATED_TEXT = """
🎁 <b>Розыгрыш: {title}</b>

🎁 Приз: {prize}
{desc}

👥 Победителей: {winners}
🔒 Подписка: {channels}
🔄 Репост: {repost}
⏰ Завершится: {ends}

Нажмите «Участвовать», чтобы присоединиться!
"""

GIVEAWAY_JOINED_TEXT = "✅ Вы участвуете в розыгрыше! Удачи!"

CANT_REMOVE_SELF = "❌ Нельзя снять права самому себе!"
USER_NOT_FOUND_ERR = "❌ Пользователь не найден."
ALREADY_ADMIN = "❌ {name} уже является администратором."
ALREADY_MOD = "❌ Этот пользователь уже модератор в указанной группе."
NOT_ADMIN = "❌ Этот пользователь не является администратором."
NOT_MOD = "❌ Этот пользователь не является модератором."

# ─── Chat Admin Management ───────────────────────────────────

CHAT_ADMIN_HELP = """
👑 <b>Назначение администратора чата</b>

Отправьте ID пользователя и ID чата(ов) через пробел.
Пример:
<code>123456789 -1001234567890</code>
<code>123456789 -1001111111111 -1002222222222</code>

Администратор чата сможет управлять настройками
и рекламой только указанных чатов.
"""

CHAT_ADMIN_ADDED = "✅ <b>Администратор чата назначен!</b>\n👤 {name} (ID: <code>{user_id}</code>)\n💬 Чат: <code>{chat_id}</code>"
CHAT_ADMIN_REMOVED = "❌ <b>Администратор чата удалён</b>\n👤 ID: <code>{user_id}</code>\n💬 Чат: <code>{chat_id}</code>"

CHAT_ADMIN_LIST_HEADER = "<b>👑 Список администраторов чатов:</b>\n\n"
CHAT_ADMIN_LIST_ITEM = "👑 <b>{name}</b>\n   └ @{username} | ID: <code>{user_id}</code>\n   └ Чаты ({total}): {chats}\n"
NO_CHAT_ADMINS = "📭 Нет администраторов чатов."
