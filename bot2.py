import asyncio
import logging
import json
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

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

# === СТУПЕНИ БОЕВОГО ПРОПУСКА (BATTLE PASS) ===
BP_LEVELS = [
    {"req": 5, "type": "stars", "value": 3, "text": "3 ⭐️ Звезды"},
    {"req": 10, "type": "mult", "value": 0.06, "text": "+0.06x к множителю 📈"},
    {"req": 15, "type": "stars", "value": 5, "text": "5 ⭐️ Звёзд"},
    {"req": 20, "type": "title_mult", "value": 0.10, "title": "Любитель ⚔️", "text": "Звание «Любитель» (+0.10x к множителю) 🏅"},
    {"req": 30, "type": "stars", "value": 10, "text": "10 ⭐️ Звёзд"},
    {"req": 35, "type": "mult", "value": 0.08, "text": "+0.08x к множителю 📈"},
    {"req": 50, "type": "title_mult", "value": 0.25, "title": "Бог ⚡️", "text": "Звание «Бог» (+0.25x к множителю) 👑"}
]

# === БАЗА ДАННЫХ ===
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
                data["promocodes"] = default_promos
            if "tasks" not in data:
                data["tasks"] = {
                    "1": {"url": "https://t.me/femboyvu", "stars": 3}
                }
            if "ADMIN" not in data["promocodes"]:
                data["promocodes"]["ADMIN"] = {"stars": 7, "max_uses": 1, "used_by": []}
            if "CEYS" not in data["promocodes"]:
                data["promocodes"]["CEYS"] = {"min_stars": 1, "max_stars": 6, "max_uses": 500, "used_by": []}
                save_db(data)
            return data
    except Exception:
        return {"users": {}, "promocodes": default_promos, "tasks": {}}

def save_db(db_data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=4)

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
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎫 Боевой Пропуск")],
        [KeyboardButton(text="🎁 Промокоды"), KeyboardButton(text="📋 Задания")],
        [KeyboardButton(text="🛠 Поддержка")]
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
            "balance": 0,
            "referrals": 0,
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
        if "ref_bonus_given" not in db["users"][user_id]:
            db["users"][user_id]["ref_bonus_given"] = False
        if "claimed_bp" not in db["users"][user_id]:
            db["users"][user_id]["claimed_bp"] = []
        if "completed_tasks" not in db["users"][user_id]:
            db["users"][user_id]["completed_tasks"] = []
        if "is_banned" not in db["users"][user_id]:
            db["users"][user_id]["is_banned"] = False
        if "extra_mult" not in db["users"][user_id]:
            db["users"][user_id]["extra_mult"] = 0.0
        if "custom_title" not in db["users"][user_id]:
            db["users"][user_id]["custom_title"] = None
        if not db["users"][user_id].get("referred_by") and referrer_id:
            db["users"][user_id]["referred_by"] = referrer_id

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
    user_data = db["users"].get(user_id, {"balance": 0, "referrals": 0, "claimed_bp": []})
    balance = user_data.get("balance", 0)
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
    user_data = db["users"].get(user_id, {"balance": 0, "referrals": 0, "claimed_bp": []})
    balance = user_data.get("balance", 0)
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
    
    if is_edit:
        await message_or_call.message.edit_text(bp_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_call.answer(bp_text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.text == "🎫 Боевой Пропуск")
async def bp_sec_msg(message: types.Message):
    if not await check_access(message):
        return
    await send_bp_menu(message, str(message.from_user.id), is_edit=False)

@dp.callback_query(F.data == "open_bp")
async def bp_sec_cb(call: types.CallbackQuery):
    await send_bp_menu(call, str(call.from_user.id), is_edit=True)

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
            
    save_db(db)
    await call.answer(f"🎉 Успешно! Получено: {reward_msg}", show_alert=True)
    await send_bp_menu(call, user_id, is_edit=True)

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

# === ОБРАБОТКА ВЫВОДОВ (БЕЗ АВТОВЫВОДА) ===
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

# === УПРАВЛЕНИЕ ЗАДАНИЯМИ В АДМИНКЕ ===
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
            f"⭐ Введи количество звезд для {sign} баланса юзера <code>{target_id}</code> (можно с точкой или запятой, например: <code>0.30</code>):",
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
            f"⚡️ Введи добавку к множителю (иксу) для юзера <code>{target_id}</code> (например, <code>0.5</code> или <code>1.2</code>):",
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
        f"👥 Рефералов: <code>{refs}</code>\n"
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
@dp.message(F.text & ~F.text.in_(["👤 Профиль", "🎫 Боевой Пропуск", "🎁 Промокоды", "📋 Задания", "🛠 Поддержка"]))
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
                await message.answer("❌ Звезды должны быть числом (например, 0.30), а лимит — целым числом!")
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
                await message.answer("❌ Сумма звезд должна быть числом (например, 0.30 или 1,5)!")
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
                await message.answer("❌ Введи число (например, 0.30 или 5)!")
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
            await message.answer(f"✅ Звание юзера <code>{target_id}</code> успешно изменено на: <b>{new_title}</b>", parse_mode="HTML")
            return

        elif state.startswith("admin_wait_mult_"):
            target_id = state.split("_")[3]
            user_states.pop(message.from_user.id, None)
            try:
                extra_mult = float(message.text.strip().replace(",", "."))
            except ValueError:
                await message.answer("❌ Введи число (например, 0.5)!")
                return
            if target_id not in db["users"]:
                await message.answer("❌ Ошибка: пользователь пропал из базы.")
                return
            db["users"][target_id]["extra_mult"] = extra_mult
            save_db(db)
            await message.answer(f"✅ Дополнительный икс юзера <code>{target_id}</code> установлен на: <code>+{extra_mult}x</code>", parse_mode="HTML")
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
                
                # Рандомный дроп со спец-анимацией для CEYS
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
