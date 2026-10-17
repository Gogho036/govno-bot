import asyncio
import logging
import json
import os
import random
from datetime import datetime, timezone, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, 
    LabeledPrice, PreCheckoutQuery
)

# === НАСТРОЙКИ И ДАННЫЕ ===
BOT_TOKEN = "8901920618:AAG6YWaNE1-n2_NyStLreW4VVqTZ4Wv4Rg4"

ADMIN_IDS = [8201986821, 8190977458]

WITHDRAW_CHANNEL = "@femboyvu"
SUPPORT_CHANNEL = "@prodafemboy"
CHECK_CHANNEL = "@hyisag"

SPONSORS = [
    {"name": "Спонсор 1", "url": "https://t.me/grasstj1", "check": "grasstj1"},
    {"name": "Спонсор 2", "url": "https://t.me/zuzxd", "check": "zuzxd"},
    {"name": "Спонсор 3", "url": "t.me/cnype", "check": ""}
]

JSON_FILE = "users_db.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_states = {}

# Время по Украине (Полтава/Киев: UTC+3)
def get_ukraine_time():
    return datetime.now(timezone(timedelta(hours=3)))

# Функция начисления реферала
def process_new_referral(db, ref_id):
    now = get_ukraine_time()
    today_str = now.date().isoformat()
    current_hour = now.hour

    db["users"][ref_id]["referrals"] += 1

    if db["users"][ref_id].get("daily_ref_date") != today_str:
        db["users"][ref_id]["daily_ref_date"] = today_str
        db["users"][ref_id]["daily_referrals"] = 0

    if 11 <= current_hour < 21:
        db["users"][ref_id]["daily_referrals"] += 1

# === СТУПЕНИ БОЕВОГО ПРОПУСКА (BATTLE PASS) ===
BP_LEVELS = [
    {"req": 5, "type": "stars", "value": 3, "text": "3 ⭐️ Звезды"},
    {"req": 10, "type": "mult", "value": 0.06, "text": "+0.06x к множителю 📈"},
    {"req": 15, "type": "stars", "value": 5, "text": "5 ⭐️ Звёзд"},
    {"req": 20, "type": "title_mult", "value": 0.10, "title": "Любитель ⚔️", "text": "Звание «Любитель» (+0.10x к множителю) 🏅"},
    {"req": 30, "type": "stars", "value": 10, "text": "10 ⭐️ Звёзд"},
    {"req": 35, "type": "mult", "value": 0.08, "text": "+0.08x к множителю 📈"},
    {"req": 50, "type": "title_mult", "value": 0.25, "title": "Бог ⚡️", "text": "Звание «Бог» (+0.25x к множителю) 👑"},
    {"req": 75, "type": "case", "min_stars": 1, "max_stars": 15, "text": "🎁 Кейс (1-15 звезд)"},
    {"req": 100, "type": "title_mult", "value": 0.30, "title": "Правитель 👑", "text": "Звание «Правитель» (+0.30x к множителю) 🏛"}
]

# === АТОМАРНОЕ СОХРАНЕНИЕ БАЗЫ ===
def load_db():
    default_promos = {
        "FEMBOY": {"stars": 2, "max_uses": 50, "used_by": []},
        "FEMBOY3": {"stars": 3, "max_uses": 999999, "used_by": []},
        "ADMIN": {"stars": 7, "max_uses": 1, "used_by": []},
        "CEYS": {"min_stars": 1, "max_stars": 6, "max_uses": 500, "used_by": []}
    }
    if not os.path.exists(JSON_FILE):
        default_db = {
            "users": {},
            "promocodes": default_promos,
            "tasks": {
                "1": {"url": "https://t.me/femboyvu", "stars": 3}
            },
            "giveaways": {}
        }
        save_db(default_db)
        return default_db
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data:
                data["users"] = {}
            if "promocodes" not in data:
                data["promocodes"] = default_promos
            if "tasks" not in data:
                data["tasks"] = {
                    "1": {"url": "https://t.me/femboyvu", "stars": 3}
                }
            if "giveaways" not in data:
                data["giveaways"] = {}
                
            for uid in data["users"]:
                if "daily_referrals" not in data["users"][uid]:
                    data["users"][uid]["daily_referrals"] = 0
                if "daily_ref_date" not in data["users"][uid]:
                    data["users"][uid]["daily_ref_date"] = ""
                if "balance" not in data["users"][uid]:
                    data["users"][uid]["balance"] = 0.0
                if "referrals" not in data["users"][uid]:
                    data["users"][uid]["referrals"] = 0
                if "completed_tasks" not in data["users"][uid]:
                    data["users"][uid]["completed_tasks"] = []
                if "claimed_bp" not in data["users"][uid]:
                    data["users"][uid]["claimed_bp"] = []
                if "activated_codes" not in data["users"][uid]:
                    data["users"][uid]["activated_codes"] = []
                if "is_banned" not in data["users"][uid]:
                    data["users"][uid]["is_banned"] = False
                if "extra_mult" not in data["users"][uid]:
                    data["users"][uid]["extra_mult"] = 0.0
                if "custom_title" not in data["users"][uid]:
                    data["users"][uid]["custom_title"] = None
            save_db(data)
            return data
    except Exception:
        return {"users": {}, "promocodes": default_promos, "tasks": {}, "giveaways": {}}

def save_db(db_data):
    temp_file = JSON_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=4)
    os.replace(temp_file, JSON_FILE)

# === РАСЧЁТ СТАТИСТИКИ И МНОЖИТЕЛЕЙ ===
def get_user_stats(user_data):
    refs = user_data.get("referrals", 0)
    claimed = user_data.get("claimed_bp", [])
    extra_mult = user_data.get("extra_mult", 0.0)
    
    mult = 1.0 + (refs * 0.02) + extra_mult
    title = "Новичок 🐣"
    
    for lvl in BP_LEVELS:
        if lvl["req"] in claimed:
            if lvl["type"] in ("mult", "title_mult"):
                mult += lvl["value"]
            if "title" in lvl:
                title = lvl["title"]
                
    if user_data.get("custom_title"):
        title = user_data["custom_title"]
                
    return round(mult, 2), title

# === КЛАВИАТУРЫ ===
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🏆 Дневной топ")],
        [KeyboardButton(text="🎁 Промокоды"), KeyboardButton(text="📋 Задания")],
        [KeyboardButton(text="🎰 Казино (За Звёзды)"), KeyboardButton(text="🛠 Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_check_sponsors_kb():
    kb = []
    for i, sp in enumerate(SPONSORS, 1):
        kb.append([InlineKeyboardButton(text=f"Подписаться на Спонсора {i}", url=sp["url"])])
    kb.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_withdraw_kb():
    amounts = [15, 25, 50, 100, 250, 500, 1000]
    kb = []
    row = []
    for amt in amounts:
        btn_text = "⭐ 1000 звезд (TG Premium 3 мес)" if amt == 1000 else f"⭐ {amt} звезд"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"withdraw_{amt}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_to_profile")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_admin_withdraw_kb():
    kb = [
        [
            InlineKeyboardButton(text="Подтвердить", callback_data="admin_approve"),
            InlineKeyboardButton(text="Отклонить", callback_data="admin_reject")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def is_subscribed(user_id: int) -> bool:
    for sp in SPONSORS:
        if not sp["check"]:
            continue
        try:
            member = await bot.get_chat_member(chat_id=f"@{sp['check']}", user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

# === УНИВЕРСАЛЬНАЯ ПРОВЕРКА ДОСТУПА ===
async def check_access(message: types.Message) -> bool:
    user_id = str(message.from_user.id)
    db = load_db()
    
    if user_id in db["users"] and db["users"][user_id].get("is_banned", False):
        await message.answer("❌ Ты заблокирован в этом боте!")
        return False
        
    if not await is_subscribed(message.from_user.id):
        if user_id in db["users"]:
            db["users"][user_id]["is_subscribed"] = False
            save_db(db)
        await message.answer(
            "🌟 <b>Доступ ограничен!</b>\n\n"
            "❌ Ты отписался от обязательных каналов-спонсоров!\n"
            "Чтобы пользоваться ботом, подпишись на всех спонсоров ниже:",
            reply_markup=get_check_sponsors_kb(),
            parse_mode="HTML"
        )
        return False
        
    return True

# === СТАРТ ===
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    db = load_db()

    if user_id in db["users"] and db["users"][user_id].get("is_banned", False):
        await message.answer("❌ Ты заблокирован в этом боте!")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "нет"
    first_name = message.from_user.first_name
    
    args = message.text.split()
    referrer_id = args[1] if len(args) > 1 and args[1] != user_id else None

    if user_id not in db["users"]:
        db["users"][user_id] = {
            "username": username,
            "first_name": first_name,
            "balance": 0.0,
            "referrals": 0,
            "daily_referrals": 0,
            "daily_ref_date": "",
            "referred_by": referrer_id,
            "completed_tasks": [],
            "is_subscribed": False,
            "ref_bonus_given": False,
            "activated_codes": [],
            "claimed_bp": [],
            "is_banned": False,
            "extra_mult": 0.0,
            "custom_title": None
        }
    else:
        db["users"][user_id]["username"] = username
        db["users"][user_id]["first_name"] = first_name

    save_db(db)

    if not await is_subscribed(message.from_user.id):
        db["users"][user_id]["is_subscribed"] = False
        save_db(db)
        await message.answer(
            "🌟 <b>Добро пожаловать в Фембой Старс!</b>\n\n"
            "❌ Ты не подписан на обязательные каналы-спонсоры!\n"
            "Чтобы запустить бота, подпишись на всех спонсоров ниже:",
            reply_markup=get_check_sponsors_kb(),
            parse_mode="HTML"
        )
        return

    db["users"][user_id]["is_subscribed"] = True

    if not db["users"][user_id].get("ref_bonus_given", False):
        db["users"][user_id]["ref_bonus_given"] = True
        ref_id = db["users"][user_id].get("referred_by")
        if ref_id and ref_id in db["users"]:
            process_new_referral(db, ref_id)
            ref_mult, _ = get_user_stats(db["users"][ref_id])
            earned_stars = round(2 * ref_mult, 2)
            db["users"][ref_id]["balance"] = round(db["users"][ref_id]["balance"] + earned_stars, 2)
            try:
                await bot.send_message(
                    int(ref_id), 
                    f"🎉 По твоей реферальной ссылке перешел пользователь и подписался!\nТебе начислено: <b>+{earned_stars} звезд ⭐</b> (с учетом твоего множителя {ref_mult}x)", 
                    parse_mode="HTML"
                )
            except Exception:
                pass

    save_db(db)
    await message.answer("Главное меню открыто. Выбирай раздел 👇", reply_markup=get_main_keyboard())

# === АДМИН-ПАНЕЛЬ /govno ===
@dp.message(Command("govno"))
async def govno_panel_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Слыш, ты не админ тут!")
        return

    db = load_db()
    total_users = len(db.get("users", {})) + 300  # С учетом пожелания (1450 участников)
    total_promos = len(db.get("promocodes", {}))
    total_tasks = len(db.get("tasks", {}))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🎁 Создать промокод", callback_data="adm_create_promo")],
        [InlineKeyboardButton(text="👤 Управлять пользователем", callback_data="adm_find_user")],
        [InlineKeyboardButton(text=f"📋 Управление заданиями ({total_tasks})", callback_data="adm_tasks_menu")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm_close")]
    ])

    await message.answer(
        f"👑 <b>АДМИН-ПАНЕЛЬ (GOVNO PANEL)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего юзеров: <code>{total_users}</code>\n"
        f"🎁 Активных промокодов: <code>{total_promos}</code>\n"
        f"📋 Активных заданий: <code>{total_tasks}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Выбирай нужный пункт:",
        reply_markup=kb,
        parse_mode="HTML"
    )

# === КОМАНДА РОЗЫГРЫША /apple ===
@dp.message(Command("apple"))
async def apple_giveaway_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Слыш, ты не админ тут!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ <b>Неверный формат команды!</b>\n\n"
            "Используй: <code>/apple СУММА ПОБЕДИТЕЛИ</code>\n"
            "<i>Пример: <code>/apple 50 3</code> (розыгрыш 50 звезд на баланс для 3 победителей)</i>",
            parse_mode="HTML"
        )
        return
    
    try:
        stars_amount = float(args[1].replace(",", "."))
        winners_count = int(args[2])
    except ValueError:
        await message.answer("❌ Сумма и количество победителей должны быть числами!")
        return
    
    db = load_db()
    if "giveaways" not in db:
        db["giveaways"] = {}
    
    gw_id = str(int(datetime.now().timestamp()))
    db["giveaways"][gw_id] = {
        "stars": stars_amount,
        "winners_count": winners_count,
        "participants": [],
        "status": "active"
    }
    save_db(db)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Участвовать (0)", callback_data=f"gw_join_{gw_id}")],
        [InlineKeyboardButton(text="🏆 Завершить и выбрать победителей", callback_data=f"gw_end_{gw_id}")]
    ])
    
    text = (
        f"🎁 <b>РОЗЫГРЫШ ЗВЕЗД НА БАЛАНС ВЫВОДА!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Приз: <b>{stars_amount} звезд</b> ⭐\n"
        f"🏆 Победителей: <b>{winners_count}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👇 Жми на кнопку ниже, чтобы принять участие!"
    )
    
    users = db.get("users", {})
    sent = 0
    status_msg = await message.answer(f"🚀 Запускаю розыгрыш для {len(users)} участников...")
    
    for uid in users.keys():
        try:
            await bot.send_message(int(uid), text, reply_markup=kb, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
            
    await status_msg.edit_text(f"✅ Розыгрыш успешно запущен и разослан {sent} пользователям!", parse_mode="HTML")

@dp.callback_query(F.data.startswith("gw_join_"))
async def gw_join_callback(call: types.CallbackQuery):
    gw_id = call.data.split("_")[2]
    user_id = str(call.from_user.id)
    
    db = load_db()
    giveaways = db.get("giveaways", {})
    if gw_id not in giveaways or giveaways[gw_id]["status"] != "active":
        await call.answer("❌ Этот розыгрыш уже завершен или не существует!", show_alert=True)
        return
    
    gw = giveaways[gw_id]
    if user_id in gw["participants"]:
        await call.answer("Ты уже участвуешь в этом розыгрыше! 🍀", show_alert=True)
        return
    
    gw["participants"].append(user_id)
    save_db(db)
    
    parts_count = len(gw["participants"])
    is_admin = call.from_user.id in ADMIN_IDS
    
    kb_buttons = [[InlineKeyboardButton(text=f"🎉 Участвовать ({parts_count})", callback_data=f"gw_join_{gw_id}")]]
    if is_admin:
        kb_buttons.append([InlineKeyboardButton(text="🏆 Завершить и выбрать победителей", callback_data=f"gw_end_{gw_id}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    
    await call.answer("✅ Ты успешно зарегистрирован в розыгрыше! Удачи!", show_alert=True)

@dp.callback_query(F.data.startswith("gw_end_"))
async def gw_end_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ У тебя нет прав!", show_alert=True)
        return
    
    gw_id = call.data.split("_")[2]
    db = load_db()
    giveaways = db.get("giveaways", {})
    if gw_id not in giveaways or giveaways[gw_id]["status"] != "active":
        await call.answer("❌ Розыгрыш уже завершен или не найден!", show_alert=True)
        return
    
    gw = giveaways[gw_id]
    gw["status"] = "finished"
    participants = gw["participants"]
    winners_count = gw["winners_count"]
    stars = gw["stars"]
    
    if not participants:
        save_db(db)
        await call.message.edit_text("❌ Розыгрыш завершен. Никто не принял участие.", reply_markup=None)
        return
    
    actual_winners_count = min(winners_count, len(participants))
    winners = random.sample(participants, actual_winners_count)
    
    winners_text = ""
    for w_id in winners:
        if w_id in db["users"]:
            db["users"][w_id]["balance"] = round(db["users"][w_id]["balance"] + stars, 2)
            w_name = db["users"][w_id].get("first_name", "Победитель")
            winners_text += f"• {w_name} (ID: <code>{w_id}</code>) — +{stars} звезд ⭐\n"
            try:
                await bot.send_message(int(w_id), f"🎉 <b>Поздравляю! Ты выиграл в розыгрыше по команде /apple!</b>\n\nТебе начислено: <b>+{stars} звезд ⭐</b> на баланс вывода!", parse_mode="HTML")
            except Exception:
                pass
                
    save_db(db)
    
    end_text = (
        f"🏁 <b>РОЗЫГРЫШ ЗАВЕРШЕН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Приз: <b>{stars} звезд</b>\n"
        f"👥 Всего участников: <b>{len(participants)}</b>\n"
        f"🏆 <b>Победители:</b>\n{winners_text}"
    )
    try:
        await call.message.edit_text(end_text, reply_markup=None, parse_mode="HTML")
    except Exception:
        await call.message.answer(end_text, parse_mode="HTML")
    await call.answer("✅ Победители успешно выбраны и призы начислены!", show_alert=True)

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    db = load_db()
    if user_id in db["users"] and db["users"][user_id].get("is_banned", False):
        await call.answer("❌ Ты заблокирован!", show_alert=True)
        return
    
    if await is_subscribed(call.from_user.id):
        if user_id in db["users"]:
            db["users"][user_id]["is_subscribed"] = True
            
            if not db["users"][user_id].get("ref_bonus_given", False):
                db["users"][user_id]["ref_bonus_given"] = True
                ref_id = db["users"][user_id].get("referred_by")
                if ref_id and ref_id in db["users"]:
                    process_new_referral(db, ref_id)
                    ref_mult, _ = get_user_stats(db["users"][ref_id])
                    earned_stars = round(2 * ref_mult, 2)
                    db["users"][ref_id]["balance"] = round(db["users"][ref_id]["balance"] + earned_stars, 2)
                    try:
                        await bot.send_message(
                            int(ref_id), 
                            f"🎉 По твоей реферальной ссылке перешел пользователь и подписался!\nТебе начислено: <b>+{earned_stars} звезд ⭐</b> (с учетом твоего множителя {ref_mult}x)", 
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
            save_db(db)

        await call.message.delete()
        await call.message.answer("✅ Подписка подтверждена! Добро пожаловать.", reply_markup=get_main_keyboard())
    else:
        await call.answer("❌ Ты подписался не на все обязательные каналы! Проверь список.", show_alert=True)

# === ПРОФИЛЬ ===
@dp.message(F.text == "👤 Профиль")
async def profile_sec(message: types.Message):
    if not await check_access(message):
        return

    user_id = str(message.from_user.id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    db = load_db()
    user_data = db["users"].get(user_id, {"balance": 0.0, "referrals": 0, "claimed_bp": []})
    balance = user_data.get("balance", 0.0)
    refs = user_data.get("referrals", 0)
    
    mult, title = get_user_stats(user_data)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="🎫 Боевой Пропуск", callback_data="open_bp")]
    ])

    text = (
        f"👤 <b>ТВОЙ ПРОФИЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎖 <b>Звание:</b> {title}\n"
        f"👥 <b>Приглашено друзей:</b> <code>{refs}</code>\n"
        f"⚡️ <b>Множитель наград:</b> <code>{mult}x</code>\n"
        f"⭐ <b>Баланс:</b> <code>{balance}</code> звезд\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>За каждого кента капает +0.02x к множителю!</i>\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@dp.callback_query(F.data == "withdraw_menu")
async def withdraw_menu_callback(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    db = load_db()
    balance = db["users"].get(user_id, {}).get("balance", 0.0)
    text = (
        f"💸 <b>Раздел вывода звезд</b>\n\n"
        f"⭐ Твой баланс: <code>{balance}</code> звезд\n"
        f"Выбери сумму или товар для вывода:"
    )
    await call.message.edit_text(text, reply_markup=get_withdraw_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    db = load_db()
    user_data = db["users"].get(user_id, {"balance": 0.0, "referrals": 0, "claimed_bp": []})
    balance = user_data.get("balance", 0.0)
    refs = user_data.get("referrals", 0)
    
    mult, title = get_user_stats(user_data)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="🎫 Боевой Пропуск", callback_data="open_bp")]
    ])

    text = (
        f"👤 <b>ТВОЙ ПРОФИЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎖 <b>Звание:</b> {title}\n"
        f"👥 <b>Приглашено друзей:</b> <code>{refs}</code>\n"
        f"⚡️ <b>Множитель наград:</b> <code>{mult}x</code>\n"
        f"⭐ <b>Баланс:</b> <code>{balance}</code> звезд\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>За каждого кента капает +0.02x к множителю!</i>\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

# === КАЗИНО (ИГРА ТОЛЬКО ЗА НАСТОЯЩИЕ TELEGRAM STARS - XTR) ===
@dp.message(F.text == "🎰 Казино (За Звёзды)")
async def casino_main_menu(message: types.Message):
    if not await check_access(message):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴/🔵 Красное или Синее", callback_data="cas_init_1")],
        [InlineKeyboardButton(text="🎯 Кольцо", callback_data="cas_init_2")]
    ])

    text = (
        f"🎰 <b>ИГРОВОЕ КАЗИНО ФЕМОК</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>ВНИМАНИЕ!</b> Игра идет ТОЛЬКО на настоящие Telegram Stars ⭐!\n"
        f"Баланс бота использовать нельзя. При каждой ставке выставляется счет на покупку реальных звезд.\n\n"
        f"Выбирай режим игры ниже:"
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "casino_main")
async def casino_main_cb(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴/🔵 Красное или Синее", callback_data="cas_init_1")],
        [InlineKeyboardButton(text="🎯 Кольцо", callback_data="cas_init_2")]
    ])
    await call.message.edit_text(
        "🎰 <b>ИГРОВОЕ КАЗИНО ФЕМОК</b>\n\nВыбирай режим игры (оплата настоящими звездами XTR):",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("cas_init_"))
async def cas_init_game(call: types.CallbackQuery):
    game_num = call.data.split("_")[2]
    user_states[call.from_user.id] = f"wait_stars_pay_g{game_num}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в казино", callback_data="casino_main")]
    ])
    
    descs = {
        "1": "🔴🔵 <b>Игра 1: Красное или Синее</b>\n\n• Красный: +0.30x выигрыш к ставке.\n• Синий: риск поделить текущий баланс пополам или выбить куш (2.0x).\n\nВведи количество НАСТОЯЩИХ ЗВЕЗД для оплаты и игры:",
        "2": "🎯 <b>Игра 2: Кольцо</b>\n\n• Ставишь «Не попаду» и промахиваешься: 1.10x выигрыш.\n• Ставишь «Попаду» и попадаешь: 2x выигрыш!\n• Ошибка: часть баланса сгорает.\n\nВведи количество НАСТОЯЩИХ ЗВЕЗД для оплаты и игры:"
    }
    await call.message.edit_text(descs[game_num], reply_markup=kb, parse_mode="HTML")

# === ДНЕВНОЙ ТОП (С 11:00 ДО 21:00) ===
@dp.message(F.text == "🏆 Дневной топ")
async def daily_top_sec(message: types.Message):
    if not await check_access(message):
        return
    
    now = get_ukraine_time()
    current_hour = now.hour
    today_str = now.date().isoformat()
    
    if current_hour < 11:
        await message.answer("⏳ <b>Дневной топ</b>\n\n❌ Конкурс ещё не начался! Старт каждый день ровно в 11:00 по Полтаве.", parse_mode="HTML")
        return
    elif current_hour >= 21:
        await message.answer("⏳ <b>Дневной топ</b>\n\n❌ Конкурс на сегодня уже закончился! Ждём завтра в 11:00.", parse_mode="HTML")
        return

    db = load_db()
    users = db.get("users", {})
    
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("daily_referrals", 0) if x[1].get("daily_ref_date") == today_str else 0,
        reverse=True
    )[:10]
    
    text = (
        f"🏆 <b>ДНЕВНОЙ ТОП ПО РЕФЕРАЛАМ</b>\n"
        f"🕒 <i>Конкурс активен ежедневно с 11:00 до 21:00!</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎁 <b>Награды дня:</b>\n"
        f"🥇 1 место: 50 звезд ⭐\n"
        f"🥈 2 место: 25 звезд ⭐\n"
        f"🥉 3 место: 15 звезд ⭐\n"
        f"4️⃣ 4 место: 10 звезд ⭐\n"
        f"5️⃣ 5 место: 5 звезд ⭐\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Топ-10 участников за сегодня:</b>\n\n"
    )
    
    active_sorted = [u for u in sorted_users if u[1].get("daily_ref_date") == today_str and u[1].get("daily_referrals", 0) > 0]
    
    if not active_sorted:
        text += "<i>Сегодня пока никто никого не пригласил. Ворвись в топ первым!</i>"
    else:
        for i, (uid, udata) in enumerate(active_sorted, 1):
            name = udata.get("first_name", "Без имени")
            username = udata.get("username", "нет")
            daily_refs = udata.get("daily_referrals", 0)
            
            medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"<b>{i}.</b>"))
            text += f"{medal} {name} ({username}) — <b>{daily_refs}</b> реф. за сегодня\n"
    
    await message.answer(text, parse_mode="HTML")

# === ФОНОВЫЙ ПЛАНИРОВЩИК (СТАРТ 11:00, ИТОГИ 21:00) ===
async def daily_contest_scheduler():
    last_notified_start = None
    last_notified_end = None
    while True:
        now = get_ukraine_time()
        current_date = now.date()
        today_str = current_date.isoformat()
        hour = now.hour
        minute = now.minute
        
        if hour == 11 and minute == 0 and last_notified_start != current_date:
            last_notified_start = current_date
            db = load_db()
            for uid in db.get("users", {}).keys():
                try:
                    await bot.send_message(int(uid), "🚀 <b>Дневной конкурс по рефералам начался!</b> Залетай в бот, забирай ссылку и рви в топ за звездами!", parse_mode="HTML")
                    await asyncio.sleep(0.04)
                except Exception:
                    pass
                    
        if hour == 21 and minute == 0 and last_notified_end != current_date:
            last_notified_end = current_date
            db = load_db()
            users = db.get("users", {})
            
            sorted_users = sorted(
                users.items(),
                key=lambda x: x[1].get("daily_referrals", 0) if x[1].get("daily_ref_date") == today_str else 0,
                reverse=True
            )
            
            prizes = {1: 50, 2: 25, 3: 15, 4: 10, 5: 5}
            winners_text = "🏁 <b>Дневной конкурс завершен! Итоги топ-5 за сегодня:</b>\n\n"
            
            awarded_count = 0
            for i in range(1, 6):
                if i <= len(sorted_users):
                    uid, udata = sorted_users[i - 1]
                    daily_refs = udata.get("daily_referrals", 0) if udata.get("daily_ref_date") == today_str else 0
                    if daily_refs <= 0:
                        break
                        
                    prize = prizes[i]
                    db["users"][uid]["balance"] = round(db["users"][uid]["balance"] + prize, 2)
                    name = udata.get("first_name", "Тип")
                    winners_text += f"{i} место: {name} ({daily_refs} реф.) — +{prize} звезд ⭐\n"
                    awarded_count += 1
                    try:
                        await bot.send_message(int(uid), f"🎉 <b>Поздравляю!</b> Ты занял {i} место в дневном топе и тебе автоматически начислено <b>{prize} звезд ⭐</b>!", parse_mode="HTML")
                    except Exception:
                        pass
                else:
                    break
                    
            if awarded_count == 0:
                winners_text += "<i>Никто не пригласил участников за время конкурса. Призы не выданы.</i>"
                
            save_db(db)
            
            for uid in db.get("users", {}).keys():
                try:
                    await bot.send_message(int(uid), winners_text, parse_mode="HTML")
                    await asyncio.sleep(0.04)
                except Exception:
                    pass
                    
        await asyncio.sleep(10)

# === БОЕВОЙ ПРОПУСК (BATTLE PASS) ===
async def send_bp_menu(message_or_call, user_id, is_edit=False):
    db = load_db()
    user_data = db["users"].get(user_id, {"referrals": 0, "claimed_bp": []})
    refs = user_data.get("referrals", 0)
    claimed = user_data.get("claimed_bp", [])
    mult, title = get_user_stats(user_data)
    
    bp_text = (
        f"🎫 <b>БОЕВОЙ ПРОПУСК (BATTLE PASS)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Приглашено друзей (всего): <b>{refs}</b>\n"
        f"🎖 Твоё звание: <b>{title}</b>\n"
        f"⚡️ Твой множитель: <code>{mult}x</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    kb_buttons = []
    for lvl in BP_LEVELS:
        req = lvl["req"]
        desc = lvl["text"]
        
        if req in claimed:
            status = "✅ [Забрано]"
        elif refs >= req:
            status = "🟢 [Доступно]"
            kb_buttons.append([InlineKeyboardButton(text=f"🎁 Забрать за {req} друзей", callback_data=f"bp_claim_{req}")])
        else:
            status = f"🔒 [{refs}/{req}]"
            
        bp_text += f"{status} <b>{req} Друзей</b> — {desc}\n"
        
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_to_profile")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    if is_edit:
        await message_or_call.message.edit_text(bp_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_call.answer(bp_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "open_bp")
async def bp_sec_cb(call: types.CallbackQuery):
    await send_bp_menu(call, str(call.from_user.id), is_edit=True)

@dp.callback_query(F.data.startswith("bp_claim_"))
async def bp_claim_callback(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    req = int(call.data.split("_")[2])
    
    db = load_db()
    if user_id not in db["users"]:
        db["users"][user_id] = {"referrals": 0, "claimed_bp": [], "balance": 0.0}
        
    user_data = db["users"][user_id]
    refs = user_data.get("referrals", 0)
    claimed = user_data.get("claimed_bp", [])
    
    if req in claimed:
        await call.answer("❌ Ты уже забрал эту награду!", show_alert=True)
        return
        
    if refs < req:
        await call.answer(f"❌ Недостаточно рефералов! Нужно {req}, у тебя {refs}.", show_alert=True)
        return
        
    target_lvl = next((l for l in BP_LEVELS if l["req"] == req), None)
    if not target_lvl:
        await call.answer("❌ Ошибка награды!", show_alert=True)
        return
        
    claimed.append(req)
    user_data["claimed_bp"] = claimed
    
    reward_msg = ""
    if target_lvl["type"] == "stars":
        stars = target_lvl["value"]
        user_data["balance"] = round(user_data["balance"] + stars, 2)
        reward_msg = f"+{stars} ⭐️ звезд"
    elif target_lvl["type"] in ("mult", "title_mult"):
        bonus = target_lvl["value"]
        reward_msg = f"+{bonus}x к множителю"
        if "title" in target_lvl:
            reward_msg += f" и звание «{target_lvl['title']}»"
    elif target_lvl["type"] == "case":
        await call.message.edit_text("🎁 <b>Открываем секретный кейс за 75 рефералов...</b>\n\n🎲 Крутим рулетку: 2 ⭐", parse_mode="HTML")
        await asyncio.sleep(0.4)
        await call.message.edit_text("🎁 <b>Открываем секретный кейс за 75 рефералов...</b>\n\n🎲 Крутим рулетку: 7 ⭐", parse_mode="HTML")
        await asyncio.sleep(0.4)
        await call.message.edit_text("🎁 <b>Открываем секретный кейс за 75 рефералов...</b>\n\n🎲 Крутим рулетку: 12 ⭐", parse_mode="HTML")
        await asyncio.sleep(0.4)
        
        reward = random.randint(target_lvl["min_stars"], target_lvl["max_stars"])
        user_data["balance"] = round(user_data["balance"] + reward, 2)
        save_db(db)
        
        await call.message.edit_text(
            f"🎉 <b>Кейс успешно открыт!</b>\n\n"
            f"⭐ Тебе выпало: <b>{reward}</b> звезд из кейса за 75 рефералов!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад в Боевой Пропуск", callback_data="open_bp")]])
        )
        return
            
    save_db(db)
    await call.answer(f"🎉 Успешно! Получено: {reward_msg}", show_alert=True)
    await send_bp_menu(call, user_id, is_edit=True)

# === СИСТЕМА ЗАДАНИЙ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===
async def show_next_task(message_or_call, user_id, is_edit=False):
    db = load_db()
    if user_id not in db["users"]:
        db["users"][user_id] = {"completed_tasks": [], "balance": 0.0}
        save_db(db)
    
    completed = db["users"][user_id].get("completed_tasks", [])
    tasks = db.get("tasks", {})
    
    next_task_id = None
    next_task_data = None
    
    for tid, tdata in tasks.items():
        if tid not in completed:
            next_task_id = tid
            next_task_data = tdata
            break
            
    if not next_task_data:
        text = "📋 <b>Задания:</b>\n\n🎉 Ты выполнил все доступные задания! Ожидай новые."
        if is_edit:
            await message_or_call.message.edit_text(text, reply_markup=None, parse_mode="HTML")
        else:
            await message_or_call.answer(text, reply_markup=None, parse_mode="HTML")
        return

    url = next_task_data["url"]
    stars = next_task_data["stars"]
    
    text = (
        f"📋 <b>ДОСТУПНОЕ ЗАДАНИЕ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Награда: <b>{stars} звезд</b>\n\n"
        f"<i>Нажми кнопку ниже, перейди по ссылке, выполни задание, а затем нажми «Подтвердить выполнение»!</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Перейти к заданию", url=url)],
        [InlineKeyboardButton(text="✅ Подтвердить выполнение", callback_data=f"task_conf_{next_task_id}")]
    ])
    
    if is_edit:
        await message_or_call.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await message_or_call.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(F.text == "📋 Задания")
async def tasks_sec_msg(message: types.Message):
    if not await check_access(message):
        return
    await show_next_task(message, str(message.from_user.id), is_edit=False)

@dp.callback_query(F.data.startswith("task_conf_"))
async def task_confirm_callback(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    task_id = call.data.split("_")[2]
    
    db = load_db()
    if user_id not in db["users"]:
        db["users"][user_id] = {"completed_tasks": [], "balance": 0.0}
        
    tasks = db.get("tasks", {})
    if task_id not in tasks:
        await call.answer("❌ Это задание больше не актуально!", show_alert=True)
        return
        
    completed = db["users"][user_id].get("completed_tasks", [])
    if task_id in completed:
        await call.answer("❌ Ты уже выполнил это задание!", show_alert=True)
        return
        
    task_reward = tasks[task_id]["stars"]
    db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + task_reward, 2)
    completed.append(task_id)
    db["users"][user_id]["completed_tasks"] = completed
    save_db(db)
    
    await call.answer(f"🎉 Задание выполнено! Начислено: +{task_reward} звезд ⭐", show_alert=True)
    await show_next_task(call, user_id, is_edit=True)

# === ПРОМОКОДЫ ===
@dp.message(F.text == "🎁 Промокоды")
async def promo_sec(message: types.Message):
    if not await check_access(message):
        return
    user_states[message.from_user.id] = "promo"
    await message.answer("🎁 Введи промокод:", parse_mode="HTML")

# === ПОДДЕРЖКА ===
@dp.message(F.text == "🛠 Поддержка")
async def support_sec(message: types.Message):
    if not await check_access(message):
        return
    user_states[message.from_user.id] = "support"
    await message.answer("🛠 <b>Служба поддержки</b>\n\nНапиши своё сообщение одним текстом:", parse_mode="HTML")

@dp.callback_query(F.data.startswith("supp_ans_"))
async def support_answer_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ У тебя нет прав!", show_alert=True)
        return
    target_id = call.data.split("_")[2]
    user_states[call.from_user.id] = f"supp_reply_{target_id}"
    
    try:
        await bot.send_message(
            call.from_user.id,
            f"✍️ Напиши ответ для пользователя с ID <code>{target_id}</code> одним сообщением:",
            parse_mode="HTML"
        )
    except Exception:
        await call.answer("❌ Напиши сначала боту в ЛС, чтобы он мог тебе писать!", show_alert=True)
        return
        
    await call.answer("✅ Перейди в личные сообщения с ботом!", show_alert=True)

# === ОБРАБОТКА ВЫВОДОВ ===
@dp.callback_query(F.data.startswith("withdraw_"))
async def process_withdraw(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    amount = float(call.data.split("_")[1])
    
    db = load_db()
    if user_id in db["users"] and db["users"][user_id].get("is_banned", False):
        await call.answer("❌ Ты заблокирован!", show_alert=True)
        return

    balance = db["users"].get(user_id, {}).get("balance", 0.0)

    if balance < amount:
        await call.answer(f"❌ Недостаточно средств! У тебя {balance} звезд, а нужно {amount}.", show_alert=True)
        return

    db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] - amount, 2)
    save_db(db)

    user_name = call.from_user.full_name
    username = f"@{call.from_user.username}" if call.from_user.username else "нет юзернейма"
    item_desc = "Telegram Premium на 3 месяца 🌟" if amount == 1000 else f"{amount} звезд"

    try:
        await bot.send_message(
            WITHDRAW_CHANNEL,
            f"🚨 <b>Новая заявка на вывод!</b>\n\n"
            f"🆔 ID: {user_id}\n"
            f"👤 Пользователь: {user_name} ({username})\n"
            f"⭐ Сумма: {amount} звезд\n"
            f"🎁 Товар: {item_desc}",
            reply_markup=get_admin_withdraw_kb(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка вывода: {e}")

    user_data = db["users"].get(user_id, {})
    activated_promos = user_data.get("activated_codes", [])
    promos_str = ", ".join(activated_promos) if activated_promos else "нет"

    referrals_list = []
    for uid, uinfo in db["users"].items():
        if uinfo.get("referred_by") == user_id:
            ref_uname = uinfo.get("username", "нет юзернейма")
            ref_fname = uinfo.get("first_name", "без имени")
            referrals_list.append(f"• ID: {uid} | {ref_fname} ({ref_uname})")

    ref_count = len(referrals_list)
    refs_formatted = "\n".join(referrals_list) if referrals_list else "нет рефералов"

    try:
        check_msg = (
            f"🔍 <b>Проверка пользователя на накрутку / бота!</b>\n\n"
            f"🆔 ID: {user_id}\n"
            f"👤 Имя: {user_name}\n"
            f"🏷 Юзернейм: {username}\n"
            f"⭐ Выводит: {amount} звезд ({item_desc})\n\n"
            f"👥 Всего рефералов: {ref_count}\n"
            f"📋 Список рефералов:\n{refs_formatted}\n\n"
            f"🎁 Использованные промокоды: {promos_str}"
        )
        await bot.send_message(CHECK_CHANNEL, check_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка проверки: {e}")

    await call.message.edit_text(
        f"✅ <b>Заявка успешно создана!</b>\n\n"
        f"С вашего баланса списано: <code>{amount}</code> звезд ⭐\n"
        f"Выбран товар: <code>{item_desc}</code>\n"
        f"Заявка отправлена на ручную проверку в канал <code>{WITHDRAW_CHANNEL}</code>.",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.in_(["admin_approve", "admin_reject"]))
async def handle_admin_withdraw_buttons(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ У тебя нет прав для управления заявками!", show_alert=True)
        return

    original_text = call.message.text

    if call.data == "admin_approve":
        new_text = f"{original_text}\n\nСтатус: ✅ Подтверждено администратором"
        await call.message.edit_text(new_text, reply_markup=None)
        await call.answer("✅ Заявка подтверждена!")

    elif call.data == "admin_reject":
        new_text = f"{original_text}\n\nСтатус: ❌ Отклонено"
        await call.message.edit_text(new_text, reply_markup=None)
        await call.answer("❌ Статус изменён на Отклонено!")

# === ОБРАБОТКА ОПЛАТЫ НАСТОЯЩИХ ЗВЕЗД В КАЗИНО ===
@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment = message.successful_payment
    paid_stars = payment.total_amount
    payload = payment.invoice_payload
    user_id = str(message.from_user.id)
    db = load_db()

    if payload.startswith("cas_g1_"):
        choice = payload.split("_")[2]
        win = random.choice([True, False])
        if choice == "red":
            if win:
                win_amount = round(paid_stars * 1.30, 2)
                db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + win_amount, 2)
                msg = f"🔴 <b>Красное Выиграло!</b>\n\n🎉 Вы получили <b>+{win_amount} звезд</b> на баланс вывода!"
            else:
                msg = f"🔴 <b>Красное Проиграло!</b>\n\n❌ Твои {paid_stars} настоящих звезд сгорели."
        else:
            if win:
                win_amount = round(paid_stars * 2.0, 2)
                db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + win_amount, 2)
                msg = f"🔵 <b>Синее Выиграло!</b>\n\n🎉 Вы выбили удвоение: <b>+{win_amount} звезд</b> на баланс!"
            else:
                cur_bal = db["users"][user_id].get("balance", 0.0)
                db["users"][user_id]["balance"] = round(cur_bal / 2, 2)
                msg = f"🔵 <b>Синее Проиграло!</b>\n\n⚠️ Твой баланс вывода уменьшен вдвое: <code>{db['users'][user_id]['balance']}</code> звезд."

    elif payload.startswith("cas_g2_"):
        choice = payload.split("_")[2]
        is_hit = random.choice([True, False])
        if choice == "miss":
            if not is_hit:
                win_amount = round(paid_stars * 1.10, 2)
                db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + win_amount, 2)
                msg = f"🎯❌ <b>Промах! Ты угадал!</b>\n\n🎉 Забрал <b>+{win_amount} звезд</b> (1.10x) на баланс!"
            else:
                cur_bal = db["users"][user_id].get("balance", 0.0)
                db["users"][user_id]["balance"] = round(cur_bal / 2, 2)
                msg = f"🎯⚠️ <b>Мяч попал в кольцо!</b> Ты проиграл.\n\n📉 Баланс уменьшен вдвое: <code>{db['users'][user_id]['balance']}</code> звезд."
        else:
            if is_hit:
                win_amount = round(paid_stars * 2.0, 2)
                db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + win_amount, 2)
                msg = f"🎯🔥 <b>Точное попадание!</b>\n\n🎉 Забрал <b>+{win_amount} звезд</b> (2.0x) на баланс!"
            else:
                cur_bal = db["users"][user_id].get("balance", 0.0)
                lost = round(paid_stars / 2, 2)
                db["users"][user_id]["balance"] = round(max(0.0, cur_bal - lost), 2)
                msg = f"🎯❌ <b>Промах!</b>\n\n📉 Списано <b>-{lost} звезд</b> с баланса."

    save_db(db)
    await message.answer(msg, parse_mode="HTML", reply_markup=get_main_keyboard())

# === ОБРАБОТЧИКИ АДМИН-ПАНЕЛИ ===
@dp.callback_query(F.data == "adm_stats")
async def adm_stats_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    db = load_db()
    users = db.get("users", {})
    total = len(users) + 300  # С учетом пожелания (1450 участников)
    banned = sum(1 for u in users.values() if u.get("is_banned", False))
    subscribed = sum(1 for u in users.values() if u.get("is_subscribed", False))

    text = (
        f"📊 <b>РАСШИРЕННАЯ СТАТИСТИКА БОТА</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего в базе: <code>{total}</code>\n"
        f"🟢 Подписаны на спонсоров: <code>{subscribed}</code>\n"
        f"🔴 Заблокировано: <code>{banned}</code>\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="adm_back")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "adm_create_promo")
async def adm_create_promo_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states[call.from_user.id] = "admin_wait_promo"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_back")]
    ])
    await call.message.edit_text(
        "🎁 <b>Создание промокода</b>\n\n"
        "Отправь в чат данные в таком формате:\n"
        "<code>КОД СТАРЫ ЛИМИТ</code>\n\n"
        "<i>Пример: <code>BONUS 0.5 100</code> или <code>BONUS 2,5 50</code></i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "adm_find_user")
async def adm_find_user_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states[call.from_user.id] = "admin_wait_user_query"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_back")]
    ])
    await call.message.edit_text(
        "👤 <b>Управление пользователем</b>\n\n"
        "Введи <b>ID</b> пользователя или его <b>Юзернейм</b> (например, <code>@username</code> или просто <code>8201986821</code>):",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "adm_tasks_menu")
async def adm_tasks_menu_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    db = load_db()
    tasks = db.get("tasks", {})

    text = f"📋 <b>УПРАВЛЕНИЕ ЗАДАНИЯМИ</b>\n━━━━━━━━━━━━━━━━━━\nАктивных заданий: <b>{len(tasks)}</b>\n\n"
    
    kb_buttons = []
    for tid, tdata in tasks.items():
        text += f"• ID: <code>{tid}</code> | Награда: {tdata['stars']} ⭐ | <a href='{tdata['url']}'>Ссылка</a>\n"
        kb_buttons.append([InlineKeyboardButton(text=f"🗑 Удалить задание #{tid}", callback_data=f"adm_del_task_{tid}")])

    kb_buttons.append([InlineKeyboardButton(text="➕ Добавить задание", callback_data="adm_add_task_start")])
    kb_buttons.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="adm_back")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@dp.callback_query(F.data == "adm_add_task_start")
async def adm_add_task_start_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states[call.from_user.id] = "admin_wait_task_data"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_tasks_menu")]
    ])
    await call.message.edit_text(
        "➕ <b>Добавление задания</b>\n\n"
        "Отправь в чат данные в таком формате:\n"
        "<code>ССЫЛКА ЗВЕЗДЫ</code>\n\n"
        "<i>Пример: <code>https://t.me/femboyvu 0.30</code> или <code>https://t.me/femboyvu 1,5</code></i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("adm_del_task_"))
async def adm_del_task_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    tid = call.data.split("_")[3]
    db = load_db()
    if tid in db.get("tasks", {}):
        db["tasks"].pop(tid)
        save_db(db)
        await call.answer("✅ Задание успешно удалено!", show_alert=True)
    else:
        await call.answer("❌ Задание не найдено!", show_alert=True)
    
    await adm_tasks_menu_callback(call)

@dp.callback_query(F.data == "adm_back")
async def adm_back_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states.pop(call.from_user.id, None)
    db = load_db()
    total_users = len(db.get("users", {})) + 300
    total_promos = len(db.get("promocodes", {}))
    total_tasks = len(db.get("tasks", {}))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🎁 Создать промокод", callback_data="adm_create_promo")],
        [InlineKeyboardButton(text="👤 Управлять пользователем", callback_data="adm_find_user")],
        [InlineKeyboardButton(text=f"📋 Управление заданиями ({total_tasks})", callback_data="adm_tasks_menu")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm_close")]
    ])
    await call.message.edit_text(
        f"👑 <b>АДМИН-ПАНЕЛЬ (GOVNO PANEL)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего юзеров: <code>{total_users}</code>\n"
        f"🎁 Активных промокодов: <code>{total_promos}</code>\n"
        f"📋 Активных заданий: <code>{total_tasks}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Выбирай нужный пункт:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "adm_close")
async def adm_close_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states.pop(call.from_user.id, None)
    await call.message.delete()

@dp.callback_query(F.data.startswith("adm_user_act_"))
async def adm_user_action_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    parts = call.data.split("_")
    action = parts[3]
    target_id = parts[4]

    db = load_db()
    if target_id not in db["users"]:
        await call.answer("❌ Пользователь не найден в базе!", show_alert=True)
        return

    if action == "ban":
        current_status = db["users"][target_id].get("is_banned", False)
        db["users"][target_id]["is_banned"] = not current_status
        save_db(db)
        new_status_text = "разбанен 🟢" if current_status else "забанен 🔴"
        await call.answer(f"✅ Пользователь успешно {new_status_text}!", show_alert=True)
        await show_user_admin_card(call.message, target_id, is_edit=True)
    elif action in ("add", "sub"):
        user_states[call.from_user.id] = f"admin_balance_{action}_{target_id}"
        sign = "+" if action == "add" else "-"
        await call.message.answer(
            f"⭐ Введи количество звезд для {sign} баланса юзера <code>{target_id}</code>:",
            parse_mode="HTML"
        )
        await call.answer()
    elif action == "title":
        user_states[call.from_user.id] = f"admin_wait_title_{target_id}"
        await call.message.answer(
            f"🎖 Введи новое звание для юзера <code>{target_id}</code> (текстом):",
            parse_mode="HTML"
        )
        await call.answer()
    elif action == "mult":
        user_states[call.from_user.id] = f"admin_wait_mult_{target_id}"
        await call.message.answer(
            f"⚡️ Введи добавку к множителю для юзера <code>{target_id}</code>:",
            parse_mode="HTML"
        )
        await call.answer()

async def show_user_admin_card(message_or_call, target_id, is_edit=False):
    db = load_db()
    uinfo = db["users"][target_id]
    uname = uinfo.get("username", "нет")
    fname = uinfo.get("first_name", "нет")
    balance = uinfo.get("balance", 0.0)
    refs = uinfo.get("referrals", 0)
    extra_mult = uinfo.get("extra_mult", 0.0)
    custom_title = uinfo.get("custom_title", "нет")
    banned = uinfo.get("is_banned", False)
    ban_text = "Разбанить 🟢" if banned else "Забанить 🔴"

    text = (
        f"👤 <b>КАРТОЧКА ПОЛЬЗОВАТЕЛЯ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"👤 Имя: {fname}\n"
        f"🏷 Юзернейм: {uname}\n"
        f"⭐ Баланс: <code>{balance}</code> звезд\n"
        f"👥 Рефералов (всего): <code>{refs}</code>\n"
        f"⚡️ Доп. икс: <code>+{extra_mult}x</code>\n"
        f"🎖 Кастом. звание: <code>{custom_title}</code>\n"
        f"📌 Статус: {'🔴 Заблокирован' if banned else '🟢 Активен'}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Дать звезды", callback_data=f"adm_user_act_add_{target_id}"),
            InlineKeyboardButton(text="➖ Забрать звезды", callback_data=f"adm_user_act_sub_{target_id}")
        ],
        [
            InlineKeyboardButton(text="🎖 Дать звание", callback_data=f"adm_user_act_title_{target_id}"),
            InlineKeyboardButton(text="⚡️ Дать иксы", callback_data=f"adm_user_act_mult_{target_id}")
        ],
        [
            InlineKeyboardButton(text=ban_text, callback_data=f"adm_user_act_ban_{target_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад в меню", callback_data="adm_back")
        ]
    ])

    if is_edit:
        await message_or_call.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_call.answer(text, reply_markup=kb, parse_mode="HTML")

# === ТЕКСТОВЫЕ СОСТОЯНИЯ И ОПЛАТА КАЗИНО ===
@dp.message(F.text & ~F.text.in_(["👤 Профиль", "🏆 Дневной топ", "🎁 Промокоды", "📋 Задания", "🎰 Казино (За Звёзды)", "🛠 Поддержка"]))
async def text_handler(message: types.Message):
    user_id = str(message.from_user.id)
    db = load_db()
    if user_id in db["users"] and db["users"][user_id].get("is_banned", False):
        return

    state = user_states.get(message.from_user.id)

    if state and state.startswith("wait_stars_pay_g"):
        game_num = state.split("_g")[1]
        user_states.pop(message.from_user.id, None)

        try:
            amount = int(message.text.strip())
            if amount <= 0:
                raise ValueError()
        except ValueError:
            await message.answer("❌ Введи целое число НАСТОЯЩИХ звезд (например: <code>5</code> или <code>10</code>):", parse_mode="HTML")
            return

        if game_num == "1":
            user_states[message.from_user.id] = f"cas_g1_select_color_{amount}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔴 Красный (0.30x)", callback_data=f"pay_g1_red_{amount}"),
                    InlineKeyboardButton(text="🔵 Синий (риск)", callback_data=f"pay_g1_blue_{amount}")
                ]
            ])
            await message.answer(f"🎲 Ставка: <b>{amount} настоящих звезд</b>. Выбери цвет:", reply_markup=kb, parse_mode="HTML")
            return

        elif game_num == "2":
            user_states[message.from_user.id] = f"cas_g2_select_option_{amount}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🎯 Попаду (2.0x)", callback_data=f"pay_g2_hit_{amount}"),
                    InlineKeyboardButton(text="❌ Не попаду (1.10x)", callback_data=f"pay_g2_miss_{amount}")
                ]
            ])
            await message.answer(f"🎯 Ставка: <b>{amount} настоящих звезд</b>. Выбери вариант:", reply_markup=kb, parse_mode="HTML")
            return

    if message.from_user.id in ADMIN_IDS and state:
        if state.startswith("supp_reply_"):
            target_id = state.split("_")[2]
            user_states.pop(message.from_user.id, None)
            answer_text = message.text.strip()
            
            try:
                await bot.send_message(
                    int(target_id),
                    f"🛠 <b>Ответ от Службы Поддержки</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💬 <b>Сообщение:</b>\n{answer_text}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✨ <i>Если возникнут еще вопросы — пиши снова!</i>",
                    parse_mode="HTML"
                )
                await message.answer(f"✅ Ответ успешно отправлен пользователю <code>{target_id}</code>!", parse_mode="HTML")
            except Exception as e:
                await message.answer(f"❌ Ошибка отправки пользователю: {e}")
            return

        elif state == "admin_wait_promo":
            user_states.pop(message.from_user.id, None)
            parts = message.text.strip().split()
            if len(parts) < 3:
                await message.answer("❌ Ошибка формата! Нужно: <code>КОД СТАРЫ ЛИМИТ</code>", parse_mode="HTML")
                return
            code = parts[0].upper()
            try:
                stars = float(parts[1].replace(",", "."))
                max_uses = int(parts[2])
            except ValueError:
                await message.answer("❌ Звезды должны быть числом, а лимит — целым числом!")
                return

            db["promocodes"][code] = {"stars": stars, "max_uses": max_uses, "used_by": []}
            save_db(db)
            await message.answer(f"✅ Промокод <code>{code}</code> успешно создан!", parse_mode="HTML")
            return

        elif state == "admin_wait_task_data":
            user_states.pop(message.from_user.id, None)
            parts = message.text.strip().split()
            if len(parts) < 2:
                await message.answer("❌ Ошибка формата! Нужно: <code>ССЫЛКА ЗВЕЗДЫ</code>", parse_mode="HTML")
                return
            url = parts[0]
            try:
                stars = float(parts[1].replace(",", "."))
            except ValueError:
                await message.answer("❌ Сумма звезд должна быть числом!")
                return

            tasks = db.get("tasks", {})
            new_id = str(max([int(k) for k in tasks.keys()] + [0]) + 1)
            tasks[new_id] = {"url": url, "stars": stars}
            db["tasks"] = tasks
            save_db(db)
            await message.answer(f"✅ Задание #{new_id} успешно добавлено!", parse_mode="HTML")
            return

        elif state == "admin_wait_user_query":
            user_states.pop(message.from_user.id, None)
            query = message.text.strip()
            found_id = None
            
            for uid, udata in db["users"].items():
                if uid == query or udata.get("username", "").lower() == query.lower() or udata.get("username", "").lower() == f"@{query.lower()}":
                    found_id = uid
                    break

            if not found_id:
                await message.answer("❌ Пользователь не найден!")
                return

            await show_user_admin_card(message, found_id, is_edit=False)
            return

        elif state.startswith("admin_balance_"):
            parts = state.split("_")
            action = parts[2]
            target_id = parts[3]
            user_states.pop(message.from_user.id, None)

            try:
                amount = float(message.text.strip().replace(",", "."))
            except ValueError:
                await message.answer("❌ Введи число!")
                return

            if target_id not in db["users"]:
                await message.answer("❌ Ошибка: пользователь пропал из базы.")
                return

            if action == "add":
                db["users"][target_id]["balance"] = round(db["users"][target_id]["balance"] + amount, 2)
                save_db(db)
                await message.answer(f"✅ Успешно добавлено {amount} звезд юзеру <code>{target_id}</code>!", parse_mode="HTML")
            elif action == "sub":
                db["users"][target_id]["balance"] = round(max(0.0, db["users"][target_id]["balance"] - amount), 2)
                save_db(db)
                await message.answer(f"✅ Успешно списано {amount} звезд у юзера <code>{target_id}</code>!", parse_mode="HTML")
            return

        elif state.startswith("admin_wait_title_"):
            target_id = state.split("_")[3]
            user_states.pop(message.from_user.id, None)
            new_title = message.text.strip()
            if target_id not in db["users"]:
                await message.answer("❌ Ошибка: пользователь пропал из базы.")
                return
            db["users"][target_id]["custom_title"] = new_title
            save_db(db)
            await message.answer(f"✅ Звание юзера изменено на: <b>{new_title}</b>", parse_mode="HTML")
            return

        elif state.startswith("admin_wait_mult_"):
            target_id = state.split("_")[3]
            user_states.pop(message.from_user.id, None)
            try:
                extra_mult = float(message.text.strip().replace(",", "."))
            except ValueError:
                await message.answer("❌ Введи число!")
                return
            if target_id not in db["users"]:
                await message.answer("❌ Ошибка: пользователь пропал из базы.")
                return
            db["users"][target_id]["extra_mult"] = extra_mult
            save_db(db)
            await message.answer(f"✅ Дополнительный икс юзера установлен на: <code>+{extra_mult}x</code>", parse_mode="HTML")
            return

    if state == "promo":
        user_states.pop(message.from_user.id, None)
        code = message.text.strip().upper()

        if code in db["promocodes"]:
            promo = db["promocodes"][code]
            if user_id in promo["used_by"]:
                await message.answer("❌ Ты уже активировал этот промокод!")
            elif len(promo["used_by"]) >= promo["max_uses"]:
                await message.answer("❌ У этого промокода закончился лимит активаций!")
            else:
                promo["used_by"].append(user_id)
                
                if "min_stars" in promo and "max_stars" in promo:
                    anim_msg = await message.answer("🎁 <b>Открываем кейс Ceys...</b>\n\n🎲 Крутим барабан: 1 ⭐", parse_mode="HTML")
                    await asyncio.sleep(0.4)
                    await anim_msg.edit_text("🎁 <b>Открываем кейс Ceys...</b>\n\n🎲 Крутим барабан: 3 ⭐", parse_mode="HTML")
                    await asyncio.sleep(0.4)
                    await anim_msg.edit_text("🎁 <b>Открываем кейс Ceys...</b>\n\n🎲 Крутим барабан: 5 ⭐", parse_mode="HTML")
                    await asyncio.sleep(0.4)
                    
                    reward = random.randint(promo["min_stars"], promo["max_stars"])
                    db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + reward, 2)
                    if code not in db["users"][user_id]["activated_codes"]:
                        db["users"][user_id]["activated_codes"].append(code)
                    save_db(db)
                    
                    await anim_msg.edit_text(
                        f"🎉 <b>Кейс Ceys успешно открыт!</b>\n\n"
                        f"⭐ Тебе выпало: <b>{reward}</b> звезд!",
                        parse_mode="HTML"
                    )
                else:
                    stars = promo["stars"]
                    db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + stars, 2)
                    if code not in db["users"][user_id]["activated_codes"]:
                        db["users"][user_id]["activated_codes"].append(code)
                    save_db(db)
                    await message.answer(f"🎉 Промокод активирован! Тебе начислено: <b>{promo['stars']}</b> звёзд ⭐", parse_mode="HTML")
        else:
            await message.answer("❌ Такого промокода не существует.")

    elif state == "support":
        user_states.pop(message.from_user.id, None)
        user_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "нет юзернейма"
        try:
            support_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Ответить", callback_data=f"supp_ans_{user_id}")]
            ])
            await bot.send_message(
                SUPPORT_CHANNEL,
                f"📩 <b>Новое обращение в поддержку!</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"👤 Пользователь: {user_name} ({username})\n"
                f"💬 Текст: {message.text}",
                reply_markup=support_kb,
                parse_mode="HTML"
            )
            await message.answer("✅ Твоё сообщение отправлено в поддержку!")
        except Exception:
            await message.answer("❌ Ошибка отправки в поддержку.")
    else:
        await message.answer("Используй кнопки меню ниже 👇", reply_markup=get_main_keyboard())

# --- КОЛБЭКИ ОПЛАТЫ КАЗИНО ---
@dp.callback_query(F.data.startswith("pay_g1_"))
async def pay_g1_callback(call: types.CallbackQuery):
    parts = call.data.split("_")
    choice = parts[2]
    amount = int(parts[3])
    
    prices = [LabeledPrice(label="Ставка в Красное/Синее", amount=amount)]
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title="Оплата ставки в Казино",
            description=f"Ставка {amount} настоящих звезд на {choice}",
            payload=f"cas_g1_{choice}",
            currency="XTR",
            prices=prices
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка счета: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("pay_g2_"))
async def pay_g2_callback(call: types.CallbackQuery):
    parts = call.data.split("_")
    choice = parts[2]
    amount = int(parts[3])
    
    prices = [LabeledPrice(label="Ставка в Кольцо", amount=amount)]
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title="Оплата ставки в Казино",
            description=f"Ставка {amount} настоящих звезд на {choice}",
            payload=f"cas_g2_{choice}",
            currency="XTR",
            prices=prices
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка счета: {e}", show_alert=True)

# === МИКРО ВЕБ-СЕРВЕР ДЛЯ UPTIMEROBOT ===
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    print("Бот, веб-сервер и супер-сохранения запущены!")
    await start_web_server()
    asyncio.create_task(daily_contest_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
