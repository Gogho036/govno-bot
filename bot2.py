import asyncio
import logging
import json
import os
import random
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery
)

# === НАСТРОЙКИ И ДАННЫЕ ===
BOT_TOKEN = "8901920618:AAHVa3vOt7RreOd1d-WoF1JhXvN3WPbW-hA"

ADMIN_IDS = [8201986821, 8190977458]

WITHDRAW_CHANNEL = "@femboyvu"
SUPPORT_CHANNEL = "@prodafemboy"
CHECK_CHANNEL = "@hyisag"

SPONSORS = [
    {"name": "Спонсор 1", "url": "https://t.me/grasstj1", "check": "grasstj1"},
    {"name": "Спонсор 2", "url": "https://t.me/zuzxd", "check": "zuzxd"},
    {"name": "Спонсор 3", "url": "https://t.me/femboyvu", "check": "femboyvu"}
]

JSON_FILE = "users_db.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_states = {}

# === СТУПЕНИ ОБЫЧНОГО БОЕВОГО ПРОПУСКА (BATTLE PASS) ===
BP_LEVELS = [
    {"req": 5, "type": "stars", "value": 8, "text": "8 ⭐️ Звёзд"},
    {"req": 10, "type": "case1", "text": "🧰 Кейс (1-15 ⭐️ и буст +0.01x..+0.15x)"},
    {"req": 15, "type": "title_mult", "value": 0.10, "title": "Король 👑", "text": "Звание «Король 👑» (+0.10x к множителю)"},
    {"req": 20, "type": "mult", "value": 0.05, "text": "+0.05x к множителю 📈"},
    {"req": 30, "type": "case2", "text": "🧰 Временный Кейс (+0.01..+0.10x буст на 1-24 часа)"},
    {"req": 35, "type": "stars", "value": 5, "text": "5 ⭐️ Звёзд"},
    {"req": 50, "type": "title_mult", "value": 0.25, "title": "Бог ⚡️", "text": "Звание «Бог ⚡️» (+0.25x к множителю)"}
]

# === СТУПЕНИ VIP ПРОПУСКА (VIP PASS - 40 STARS VIA TG PAY) ===
VIP_BP_COST_STARS = 40
VIP_BP_LEVELS = [
    {"req": 3, "type": "stars", "value": 15, "text": "15 ⭐️ Звёзд"},
    {"req": 7, "type": "mult", "value": 0.20, "text": "+0.20x к множителю 📈"},
    {"req": 12, "type": "stars", "value": 30, "text": "30 ⭐️ Звёзд"},
    {"req": 20, "type": "vip_case1", "text": "🎁 VIP Мега-Кейс (20-50 ⭐️ Звёзд)"},
    {"req": 35, "type": "title_mult_stars", "value": 0.35, "stars_val": 15, "title": "VIP Фембой 💎", "text": "15 ⭐️ + Звание «VIP Фембой 💎» (+0.35x)"}
]

# === БАЗА ДАННЫХ ===
def load_db():
    if not os.path.exists(JSON_FILE):
        default_db = {
            "users": {},
            "promocodes": {
                "FEMBOY": {"stars": 2, "max_uses": 50, "used_by": []},
                "FEMBOY3": {"stars": 3, "max_uses": 999999, "used_by": []},
                "ADMIN": {"stars": 7, "max_uses": 1, "used_by": []}
            },
            "tasks": {
                "1": {"url": "https://t.me/femboyvu", "stars": 3}
            }
        }
        save_db(default_db)
        return default_db
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data:
                data["users"] = {}
            if "promocodes" not in data:
                data["promocodes"] = {}
            if "tasks" not in data:
                data["tasks"] = {}
            return data
    except Exception:
        return {"users": {}, "promocodes": {}, "tasks": {}}

def save_db(db_data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=4)

# === РАСЧЁТ СТАТИСТИКИ И МНОЖИТЕЛЕЙ ===
def get_user_stats(user_data):
    refs = user_data.get("referrals", 0)
    claimed_bp = user_data.get("claimed_bp", [])
    claimed_vip = user_data.get("claimed_vip_bp", [])
    
    mult = 1.0 + (refs * 0.02)
    title = "Новичок 🐣"

    # Бусты и звания из обычного БП
    for lvl in BP_LEVELS:
        if lvl["req"] in claimed_bp:
            if lvl["type"] in ("mult", "title_mult"):
                mult += lvl.get("value", 0)
            if "title" in lvl:
                title = lvl["title"]

    # Бусты и звания из VIP БП
    for lvl in VIP_BP_LEVELS:
        if lvl["req"] in claimed_vip:
            if lvl["type"] in ("mult", "title_mult", "title_mult_stars"):
                mult += lvl.get("value", 0)
            if "title" in lvl:
                title = lvl["title"]

    # Проверка временного буста
    temp_boost = user_data.get("temp_boost", {})
    if temp_boost and "until" in temp_boost and "value" in temp_boost:
        try:
            until_dt = datetime.fromisoformat(temp_boost["until"])
            if datetime.now() < until_dt:
                mult += temp_boost["value"]
        except Exception:
            pass

    return round(mult, 2), title

# === КЛАВИАТУРЫ ===
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Промокоды")],
        [KeyboardButton(text="📋 Задания"), KeyboardButton(text="🛠 Поддержка")]
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

# === АНИМАЦИЯ КЕЙСА ===
async def animate_case_opening(call: types.CallbackQuery, case_title="🧰 КЕЙС"):
    frames = [
        f"🎰 <b>{case_title}</b>\n\n[ ❓ | ❓ | ❓ ]\n<i>Запуск рулетки...</i>",
        f"🎰 <b>{case_title}</b>\n\n[ ⚡️ | ⭐️ | 🎁 ]\n<i>Крутим барабан...</i>",
        f"🎰 <b>{case_title}</b>\n\n[ 👑 | 💎 | 🚀 ]\n<i>Замедление...</i>",
        f"🎰 <b>{case_title}</b>\n\n[ ⭐ | ✨ | 🏆 ]\n<i>Открываем...</i>"
    ]
    for frame in frames:
        try:
            await call.message.edit_text(frame, parse_mode="HTML")
            await asyncio.sleep(0.5)
        except Exception:
            pass

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
            "balance": 0,
            "referrals": 0,
            "referred_by": referrer_id,
            "completed_tasks": [],
            "is_subscribed": False,
            "ref_bonus_given": False,
            "activated_codes": [],
            "approved_withdraws": 0,
            "claimed_bp": [],
            "claimed_vip_bp": [],
            "has_vip": False,
            "temp_boost": {},
            "is_banned": False
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
            db["users"][ref_id]["referrals"] += 1
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
    total_users = len(db.get("users", {}))
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
                    db["users"][ref_id]["referrals"] += 1
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
    user_data = db["users"].get(user_id, {"balance": 0, "referrals": 0})
    balance = user_data.get("balance", 0)
    refs = user_data.get("referrals", 0)
    
    is_admin = int(user_id) in ADMIN_IDS
    has_vip = user_data.get("has_vip", False) or is_admin
    vip_status_str = "АКТИВЕН 👑 (Админ)" if is_admin else ("АКТИВЕН 👑" if has_vip else "Не куплен ❌")
    
    mult, title = get_user_stats(user_data)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="🎫 Боевой Пропуск", callback_data="open_bp")],
        [InlineKeyboardButton(text=f"👑 VIP Пропуск ({VIP_BP_COST_STARS} ⭐)", callback_data="open_vip_bp")]
    ])

    text = (
        f"👤 <b>ТВОЙ ПРОФИЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎖 <b>Звание:</b> {title}\n"
        f"👑 <b>VIP Статус:</b> {vip_status_str}\n"
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
    balance = db["users"].get(user_id, {}).get("balance", 0)
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
    user_data = db["users"].get(user_id, {"balance": 0, "referrals": 0})
    balance = user_data.get("balance", 0)
    refs = user_data.get("referrals", 0)
    
    is_admin = int(user_id) in ADMIN_IDS
    has_vip = user_data.get("has_vip", False) or is_admin
    vip_status_str = "АКТИВЕН 👑 (Админ)" if is_admin else ("АКТИВЕН 👑" if has_vip else "Не куплен ❌")
    
    mult, title = get_user_stats(user_data)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="🎫 Боевой Пропуск", callback_data="open_bp")],
        [InlineKeyboardButton(text=f"👑 VIP Пропуск ({VIP_BP_COST_STARS} ⭐)", callback_data="open_vip_bp")]
    ])

    text = (
        f"👤 <b>ТВОЙ ПРОФИЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎖 <b>Звание:</b> {title}\n"
        f"👑 <b>VIP Статус:</b> {vip_status_str}\n"
        f"👥 <b>Приглашено друзей:</b> <code>{refs}</code>\n"
        f"⚡️ <b>Множитель наград:</b> <code>{mult}x</code>\n"
        f"⭐ <b>Баланс:</b> <code>{balance}</code> звезд\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>За каждого кента капает +0.02x к множителю!</i>\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

# === ОБЫЧНЫЙ БОЕВОЙ ПРОПУСК (BATTLE PASS) ===
async def send_bp_menu(call, user_id):
    db = load_db()
    user_data = db["users"].get(user_id, {"referrals": 0, "claimed_bp": []})
    refs = user_data.get("referrals", 0)
    claimed = user_data.get("claimed_bp", [])
    mult, title = get_user_stats(user_data)
    
    bp_text = (
        f"🎫 <b>БОЕВОЙ ПРОПУСК (BATTLE PASS)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Приглашено друзей: <b>{refs}</b>\n"
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
    await call.message.edit_text(bp_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "open_bp")
async def bp_sec_cb(call: types.CallbackQuery):
    await send_bp_menu(call, str(call.from_user.id))

@dp.callback_query(F.data.startswith("bp_claim_"))
async def bp_claim_callback(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    req = int(call.data.split("_")[2])
    
    db = load_db()
    if user_id not in db["users"]:
        db["users"][user_id] = {"referrals": 0, "claimed_bp": [], "balance": 0}
        
    user_data = db["users"][user_id]
    refs = user_data.get("referrals", 0)
    claimed = user_data.get("claimed_bp", [])
    
    if req in claimed:
        await call.answer("❌ Ты уже забрал эту награду!", show_alert=True)
        return
        
    if refs < req and int(user_id) not in ADMIN_IDS:
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
    elif target_lvl["type"] == "case1":
        await animate_case_opening(call, "🧰 ОБЫЧНЫЙ КЕЙС")
        win_stars = random.randint(1, 15)
        win_boost = round(random.uniform(0.01, 0.15), 2)
        user_data["balance"] = round(user_data["balance"] + win_stars, 2)
        user_data["claimed_bp"].append(f"case1_boost_{win_boost}")
        reward_msg = f"🎉 <b>ВЫПАЛО ИЗ КЕЙСА:</b>\n\n⭐ <b>+{win_stars} Звёзд</b>\n📈 <b>+{win_boost}x к постоянному множителю!</b>"
    elif target_lvl["type"] == "case2":
        await animate_case_opening(call, "🧰 ВРЕМЕННЫЙ КЕЙС")
        win_boost = round(random.uniform(0.01, 0.10), 2)
        hours = random.randint(1, 24)
        until_dt = datetime.now() + timedelta(hours=hours)
        user_data["temp_boost"] = {
            "value": win_boost,
            "until": until_dt.isoformat()
        }
        reward_msg = f"🎉 <b>ВЫПАЛО ИЗ ВРЕМЕННОГО КЕЙСА:</b>\n\n⏳ Буст <b>+{win_boost}x на {hours} час(ов)!</b>"
            
    save_db(db)
    if "case" in target_lvl["type"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Обратно в БП", callback_data="open_bp")]])
        await call.message.edit_text(reward_msg, reply_markup=kb, parse_mode="HTML")
    else:
        await call.answer(f"🎉 Успешно! {reward_msg}", show_alert=True)
        await send_bp_menu(call, user_id)

# === VIP БОЕВОЙ ПРОПУСК ===
async def send_vip_bp_menu(call, user_id):
    db = load_db()
    user_data = db["users"].get(user_id, {"referrals": 0, "claimed_vip_bp": [], "has_vip": False})
    refs = user_data.get("referrals", 0)
    claimed = user_data.get("claimed_vip_bp", [])
    
    is_admin = int(user_id) in ADMIN_IDS
    has_vip = user_data.get("has_vip", False) or is_admin
    mult, title = get_user_stats(user_data)
    
    status_vip = "🟢 <b>БЕСПЛАТНЫЙ ДОСТУП (АДМИН)</b>" if is_admin else ("🟢 <b>АКТИВЕН</b>" if has_vip else "🔴 <b>НЕ КУПЛЕН</b>")

    vip_text = (
        f"👑 <b>VIP БОЕВОЙ ПРОПУСК</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Статус VIP: {status_vip}\n"
        f"👥 Приглашено друзей: <b>{refs}</b>\n"
        f"⚡️ Твой множитель: <code>{mult}x</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Приобрети VIP Пропуск за {VIP_BP_COST_STARS} ⭐ Telegram Stars, чтобы разблокировать доступ к эксклюзивным наградам!</i>\n\n"
    )
    
    kb_buttons = []
    if not has_vip:
        kb_buttons.append([InlineKeyboardButton(text=f"⭐ Купить VIP за {VIP_BP_COST_STARS} Telegram Stars", callback_data="buy_vip_stars")])

    for lvl in VIP_BP_LEVELS:
        req = lvl["req"]
        desc = lvl["text"]
        
        if req in claimed:
            status = "✅ [Забрано]"
        elif has_vip and refs >= req:
            status = "🟢 [Доступно]"
            kb_buttons.append([InlineKeyboardButton(text=f"👑 VIP Награда за {req} друзей", callback_data=f"vip_claim_{req}")])
        elif not has_vip:
            status = f"🔒 [VIP Заблокирован]"
        else:
            status = f"🔒 [{refs}/{req}]"
            
        vip_text += f"{status} <b>{req} Друзей</b> — {desc}\n"
        
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_to_profile")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await call.message.edit_text(vip_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "open_vip_bp")
async def vip_bp_sec_cb(call: types.CallbackQuery):
    await send_vip_bp_menu(call, str(call.from_user.id))

# === ПОКУПКА VIP НАСТОЯЩИМИ TELEGRAM STARS ===
@dp.callback_query(F.data == "buy_vip_stars")
async def buy_vip_stars_callback(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    db = load_db()
    
    if int(user_id) in ADMIN_IDS:
        await call.answer("👑 Ты админ, у тебя бесплатный доступ!", show_alert=True)
        return

    if db["users"].get(user_id, {}).get("has_vip", False):
        await call.answer("❌ У тебя уже куплен VIP Пропуск!", show_alert=True)
        return

    prices = [LabeledPrice(label="VIP Пропуск Femboy Stars", amount=VIP_BP_COST_STARS)]
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title="👑 VIP Пропуск Femboy Stars",
            description="Разблокирует эксклюзивные VIP-награды, бусты и звание!",
            payload="vip_pass_payment",
            currency="XTR",
            prices=prices,
            provider_token=""
        )
        await call.answer()
    except Exception as e:
        logging.error(f"Ошибка вызова инвойса Stars: {e}")
        await call.answer("❌ Ошибка запуска оплаты Telegram Stars!", show_alert=True)

@dp.pre_checkout_query(F.invoice_payload == "vip_pass_payment")
async def process_vip_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_vip_successful_payment(message: types.Message):
    if message.successful_payment.invoice_payload == "vip_pass_payment":
        user_id = str(message.from_user.id)
        db = load_db()
        if user_id in db["users"]:
            db["users"][user_id]["has_vip"] = True
            save_db(db)
        await message.answer(
            "🎉 <b>ПОЗДРАВЛЯЕМ! ОПЛАТА УСПЕШНА!</b>\n\n"
            "👑 Твой VIP Пропуск активирован! Заходи в Профиль -> VIP Пропуск и забирай свои эксклюзивные награды!",
            parse_mode="HTML"
        )

@dp.callback_query(F.data.startswith("vip_claim_"))
async def vip_claim_callback(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    req = int(call.data.split("_")[2])
    
    db = load_db()
    user_data = db["users"].get(user_id, {})
    is_admin = int(user_id) in ADMIN_IDS
    
    if not (user_data.get("has_vip", False) or is_admin):
        await call.answer(f"❌ Сначала купи VIP Пропуск за {VIP_BP_COST_STARS} Telegram Stars!", show_alert=True)
        return
        
    refs = user_data.get("referrals", 0)
    claimed = user_data.get("claimed_vip_bp", [])
    
    if req in claimed:
        await call.answer("❌ Ты уже забрал эту VIP награду!", show_alert=True)
        return
        
    if refs < req and not is_admin:
        await call.answer(f"❌ Недостаточно рефералов! Нужно {req}, у тебя {refs}.", show_alert=True)
        return
        
    target_lvl = next((l for l in VIP_BP_LEVELS if l["req"] == req), None)
    if not target_lvl:
        await call.answer("❌ Ошибка награды!", show_alert=True)
        return
        
    claimed.append(req)
    user_data["claimed_vip_bp"] = claimed
    
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
    elif target_lvl["type"] == "title_mult_stars":
        stars = target_lvl["stars_val"]
        bonus = target_lvl["value"]
        title = target_lvl["title"]
        user_data["balance"] = round(user_data["balance"] + stars, 2)
        reward_msg = f"+{stars} ⭐️ звёзд, звание «{title}» и +{bonus}x к множителю!"
    elif target_lvl["type"] == "vip_case1":
        await animate_case_opening(call, "🎁 VIP МЕГА-КЕЙС")
        win_stars = random.randint(20, 50)
        user_data["balance"] = round(user_data["balance"] + win_stars, 2)
        reward_msg = f"🎉 <b>ВЫПАЛО ИЗ VIP МЕГА-КЕЙСА:</b>\n\n⭐ <b>+{win_stars} Звёзд!</b>"
            
    save_db(db)
    if "case" in target_lvl["type"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Обратно в VIP БП", callback_data="open_vip_bp")]])
        await call.message.edit_text(reward_msg, reply_markup=kb, parse_mode="HTML")
    else:
        await call.answer(f"🎉 Успешно получена VIP Награда! {reward_msg}", show_alert=True)
        await send_vip_bp_menu(call, user_id)

# === СИСТЕМА ЗАДАНИЙ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===
async def show_next_task(message_or_call, user_id, is_edit=False):
    db = load_db()
    if user_id not in db["users"]:
        db["users"][user_id] = {"completed_tasks": [], "balance": 0}
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
        db["users"][user_id] = {"completed_tasks": [], "balance": 0}
        
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

# === ОБРАБОТКА ВЫВОДОВ (ТОЛЬКО РУЧНАЯ ПРОВЕРКА) ===
@dp.callback_query(F.data.startswith("withdraw_"))
async def process_withdraw(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    amount = float(call.data.split("_")[1])
    
    db = load_db()
    if user_id in db["users"] and db["users"][user_id].get("is_banned", False):
        await call.answer("❌ Ты заблокирован!", show_alert=True)
        return

    balance = db["users"].get(user_id, {}).get("balance", 0)

    if balance < amount:
        await call.answer(f"❌ Недостаточно средств! У тебя {balance} звезд, а нужно {amount}.", show_alert=True)
        return

    db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] - amount, 2)
    save_db(db)

    user_name = call.from_user.full_name
    username = f"@{call.from_user.username}" if call.from_user.username else "нет юзернейма"
    item_desc = "Telegram Premium на 3 месяца 🌟" if amount == 1000 else f"{amount} звезд"
    
    approved_count = db["users"][user_id].get("approved_withdraws", 0)

    try:
        await bot.send_message(
            WITHDRAW_CHANNEL,
            f"🚨 <b>Новая заявка на вывод!</b>\n\n"
            f"🆔 ID: {user_id}\n"
            f"👤 Пользователь: {user_name} ({username})\n"
            f"⭐ Сумма: {amount} звезд\n"
            f"🎁 Товар: {item_desc}\n"
            f"📊 Подтвержденных выводов ранее: {approved_count}",
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
    lines = original_text.split("\n")
    user_id = None
    for line in lines:
        if "🆔 ID:" in line or "ID:" in line:
            user_id = line.split("ID:")[1].strip()
            break

    if call.data == "admin_approve":
        db = load_db()
        if user_id and user_id in db["users"]:
            current_count = db["users"][user_id].get("approved_withdraws", 0) + 1
            db["users"][user_id]["approved_withdraws"] = current_count
            save_db(db)
            new_text = f"{original_text}\n\nСтатус: ✅ Подтверждено админом (Всего одобрено: {current_count})"
        else:
            new_text = f"{original_text}\n\nСтатус: ✅ Подтверждено"

        await call.message.edit_text(new_text, reply_markup=None)
        await call.answer("✅ Заявка подтверждена!")

    elif call.data == "admin_reject":
        new_text = f"{original_text}\n\nСтатус: ❌ Отклонено"
        await call.message.edit_text(new_text, reply_markup=None)
        await call.answer("❌ Статус изменён на Отклонено!")

# === ОБРАБОТЧИКИ АДМИН-ПАНЕЛИ ===
@dp.callback_query(F.data == "adm_stats")
async def adm_stats_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    db = load_db()
    users = db.get("users", {})
    total = len(users)
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
    total_users = len(db.get("users", {}))
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
            f"⭐ Введи количество звезд для {sign} баланса юзера <code>{target_id}</code> (например, <code>0.30</code>):",
            parse_mode="HTML"
        )
        await call.answer()

async def show_user_admin_card(message_or_call, target_id, is_edit=False):
    db = load_db()
    uinfo = db["users"][target_id]
    uname = uinfo.get("username", "нет")
    fname = uinfo.get("first_name", "нет")
    balance = uinfo.get("balance", 0)
    refs = uinfo.get("referrals", 0)
    banned = uinfo.get("is_banned", False)
    ban_text = "Разбанить 🟢" if banned else "Забанить 🔴"

    text = (
        f"👤 <b>КАРТОЧКА ПОЛЬЗОВАТЕЛЯ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"👤 Имя: {fname}\n"
        f"🏷 Юзернейм: {uname}\n"
        f"⭐ Баланс: <code>{balance}</code> звезд\n"
        f"👥 Рефералов: <code>{refs}</code>\n"
        f"📌 Статус: {'🔴 Заблокирован' if banned else '🟢 Активен'}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Дать звезды", callback_data=f"adm_user_act_add_{target_id}"),
            InlineKeyboardButton(text="➖ Забрать звезды", callback_data=f"adm_user_act_sub_{target_id}")
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

# === РАССЫЛКА ПО БАЗЕ (/send) ===
@dp.message(Command("send"))
async def broadcast_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Слыш, ты чё, не админ тут чтобы рассылки устраивать!")
        return

    if not message.reply_to_message:
        await message.answer(
            "❌ <b>Сделай реплай (ответ) на сообщение или пост, который хочешь разослать!</b>\n\n"
            "💡 <b>Как добавить кнопки?</b> Напиши при отправке команды:\n"
            "<code>/send</code>\n"
            "<code>Текст Кнопки - https://ссылка.com</code>",
            parse_mode="HTML"
        )
        return

    reply_markup = None
    cmd_args = message.text.split("\n")[1:]
    if cmd_args:
        inline_keyboard = []
        for line in cmd_args:
            if " - " in line:
                btn_text, btn_url = line.split(" - ", 1)
                btn_text = btn_text.strip()
                btn_url = btn_url.strip()
                if btn_url.startswith("http://") or btn_url.startswith("https://") or btn_url.startswith("t.me/"):
                    if not btn_url.startswith("http"):
                        btn_url = f"https://{btn_url}"
                    inline_keyboard.append([InlineKeyboardButton(text=btn_text, url=btn_url)])
        if inline_keyboard:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    db = load_db()
    users = db.get("users", {})
    
    if not users:
        await message.answer("❌ В базе данных пока нет ни одного пользователя!")
        return

    sent_count = 0
    blocked_count = 0

    status_msg = await message.answer(f"🚀 Запускаю рассылку для {len(users)} чел...")

    for user_id in users.keys():
        try:
            await bot.copy_message(
                chat_id=int(user_id),
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id,
                reply_markup=reply_markup
            )
            sent_count += 1
            await asyncio.sleep(0.04)
        except Exception:
            blocked_count += 1

    await status_msg.edit_text(
        f"✅ <b>Рассылка успешно завершена!</b>\n\n"
        f"📤 Дошло до типов: <code>{sent_count}</code>\n"
        f"🚫 Заблокировали бота / ушли в игнор: <code>{blocked_count}</code>",
        parse_mode="HTML"
    )

# === ТЕКСТОВЫЕ СОСТОЯНИЯ ===
@dp.message(F.text & ~F.text.in_(["👤 Профиль", "🎁 Промокоды", "📋 Задания", "🛠 Поддержка"]))
async def text_handler(message: types.Message):
    user_id = str(message.from_user.id)
    db = load_db()
    if user_id in db["users"] and db["users"][user_id].get("is_banned", False):
        return

    state = user_states.get(message.from_user.id)

    # ОБРАБОТКА СОСТОЯНИЙ АДМИНА
    if message.from_user.id in ADMIN_IDS and state:
        if state == "admin_wait_promo":
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
            await message.answer(f"✅ Промокод <code>{code}</code> успешно создан! Награда: {stars} звезд, лимит: {max_uses}.", parse_mode="HTML")
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
            await message.answer(f"✅ Задание #{new_id} успешно добавлено! Ссылка: {url}, Награда: {stars} ⭐", parse_mode="HTML")
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

    # Обычные состояния
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
                db["users"][user_id]["balance"] = round(db["users"][user_id]["balance"] + promo["stars"], 2)
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
            await bot.send_message(
                SUPPORT_CHANNEL,
                f"📩 <b>Новое обращение в поддержку!</b>\n\n🆔 ID: {user_id}\n👤 Пользователь: {user_name} ({username})\n💬 Текст: {message.text}",
                parse_mode="HTML"
            )
            await message.answer("✅ Твоё сообщение отправлено в поддержку!")
        except Exception:
            await message.answer("❌ Ошибка отправки в поддержку.")
    else:
        await message.answer("Используй кнопки меню ниже 👇", reply_markup=get_main_keyboard())

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
    print("Бот и веб-сервер запущены!")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
