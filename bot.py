# bot.py — MLBB Top-Up Bot (Manual Order ONLY)
import asyncio
import logging
import re
import sqlite3
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

SELECT_PRODUCT, ASK_IDS, ASK_PHOTO = range(3)

STATUS_MY = {
    "pending": "⏳ စောင့်နေတယ်",
    "confirmed": "✅ ငွေအတည်ပြုပြီး",
    "rejected": "❌ ပယ်ချခံရတယ်",
    "done": "🎉 ပို့ပြီး / ပြီးသွားပြီ",
}

def init_db(db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            product_key TEXT,
            product_name TEXT,
            mlbb_id TEXT,
            zone_id TEXT,
            price INTEGER,
            photo_file_id TEXT,
            status TEXT,
            created_at TEXT,
            photo_blob BLOB
        )
        """
    )
    cols = [r[1] for r in conn.execute("PRAGMA table_info(orders)")]
    if "photo_blob" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN photo_blob BLOB")
    conn.commit()
    conn.close()

def next_order_id(db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT COUNT(*) FROM orders")
    count = cur.fetchone()[0]
    conn.close()
    return f"MLBB-{count + 1:04d}"

def save_order(order, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO orders (id, user_id, username, product_key, product_name, mlbb_id, zone_id, price, photo_file_id, status, created_at, photo_blob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            order["id"],
            order["user_id"],
            order["username"],
            order["product_key"],
            order["product_name"],
            order["mlbb_id"],
            order["zone_id"],
            order["price"],
            order["photo_file_id"],
            order["status"],
            order["created_at"],
            order.get("photo_blob"),
        ),
    )
    conn.commit()
    conn.close()

def get_order(order_id, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_status(order_id, status, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

def list_orders(user_id=None, status=None, limit=10, db_path=config.DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM orders"
    params = []
    conds = []
    if user_id is not None:
        conds.append("user_id = ?")
        params.append(user_id)
    if status is not None:
        conds.append("status = ?")
        params.append(status)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    cur = conn.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def fmt_price(n):
    return f"{n:,} Ks"

def main_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            
            [InlineKeyboardButton("🎫 Weekly Pass ဝယ်မယ်", callback_data="cat_weekly")],
            [InlineKeyboardButton("📦 ငါ့ order တွေ", callback_data="my_orders")],
        ]
    )

def admin_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Order စာရင်း", callback_data="admin_orders")],
        ]
    )


def product_keyboard(keys):
    buttons = []
    for key in keys:
        p = config.PRODUCTS[key]
        buttons.append(
            [InlineKeyboardButton(f"{p['name']} — {fmt_price(p['price'])}", callback_data=f"product_{key}")]
        )
    buttons.append([InlineKeyboardButton("⬅️ နောက်သို့", callback_data="back_menu")])
    return InlineKeyboardMarkup(buttons)

def price_list_text():
    return (
        "မင်္ဂလာပါခင်ဗျာ 👋❤️\n\n"
        "MLBB Weekly Pass ဝယ်ယူအားပေးနိုင်တဲ့ ဆိုင်လေးမှ ကြိုဆိုပါတယ်ဗျ။\n\n"
        "🎫 MLBB Weekly Pass ဈေးနှုန်းများ\n\n"
        f"💎 Weekly Pass 1 ခု (7 ရက်) — {fmt_price(config.PRODUCTS['wp_1']['price'])}\n"
        f"💎 Weekly Pass 2 ခု — {fmt_price(config.PRODUCTS['wp_2']['price'])}\n"
        f"💎 Weekly Pass 3 ခု — {fmt_price(config.PRODUCTS['wp_3']['price'])}\n\n"
        "ဝယ်ယူလိုတဲ့ အရေအတွက်လေးကို အောက်မှာ ရွေးချယ်ပေးပါနော်။ 👇\n\n"
        "🙏 အားပေးမှုအတွက် ကျေးဇူးအများကြီးတင်ပါတယ်ဗျ။"
    )
    
    
        
        
    
    

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = price_list_text()
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    return SELECT_PRODUCT

async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back_menu":
        await query.edit_message_text(
            price_list_text(), reply_markup=main_menu_keyboard(), parse_mode="Markdown"
        )
        return SELECT_PRODUCT
    if data == "cat_diamond":
        await query.edit_message_text(
            "💎 Diamond က အခု မရသေးဘူး။\n🎫 Weekly Pass ပဲ ရတယ်။", reply_markup=main_menu_keyboard(),
        )
        return SELECT_PRODUCT
    if data == "cat_weekly":
        await query.edit_message_text(
            "🎫 Weekly Pass — ဘယ်နှခုယူမလဲ?\n(1 ခု = 220 Diamond, 7 ရက်အတွင်း ရတယ်)",
            reply_markup=product_keyboard(config.WEEKLY_KEYS),
        )
        return SELECT_PRODUCT
    if data == "my_orders":
        await show_my_orders(update, context)
        return SELECT_PRODUCT
    if data.startswith("product_"):
        key = data.replace("product_", "", 1)
        product = config.PRODUCTS.get(key)
        if not product:
            await query.edit_message_text("ဒီ ပစ္စည်း မရှိတော့ဘူး။ /start နဲ့ ပြန်စလိုက်ပါ။")
            return ConversationHandler.END
        if key in config.DIAMOND_KEYS:
            await query.edit_message_text(
                "💎 Diamond က အခု မရသေးဘူး။\n🎫 Weekly Pass ပဲ ရတယ်။",
                reply_markup=main_menu_keyboard(),
            )
            return SELECT_PRODUCT
        context.user_data["product_key"] = key
        context.user_data["product_name"] = product["name"]
        context.user_data["price"] = product["price"]
        await query.edit_message_text(
            f"{product['name']} — {fmt_price(product['price'])} ကို ရွေးချယ်ထားပါတယ်။\n\n"
            "အော်ဒါဆက်လက်လုပ်ဆောင်ဖို့ သင့်ရဲ့ Game ID နဲ့ Zone ID ကို ပို့ပေးပါခင်ဗျာ။ ❤️\n\n"
            "📌 ဥပမာ — 12345678 (1234)\n\n"
            "Game ID နဲ့ Zone ID ကို ဂိမ်းထဲက Profile မှာ ကြည့်ရှုနိုင်ပါတယ်။\n\n"
            "မှန်ကန်တဲ့ ID လေး ပို့ပေးဖို့ သတိပြုပေးပါနော်။ 🙏"
        )
        return ASK_IDS
    return SELECT_PRODUCT

async def ask_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    numbers = re.findall(r"\d+", text)
    if len(numbers) < 2:
        await update.message.reply_text(
            "❌ Game ID နဲ့ Zone ID နှစ်ခုလုံး လိုတယ်။ တစ်ခါတည်း ပြန်ပို့ပေးပါ။\n"
            "ဥပမာ: 12345678 (1234)"
        )
        return ASK_IDS
    mlbb_id, zone_id = numbers[0], numbers[1]
    if len(mlbb_id) < 5 or len(zone_id) < 3:
        await update.message.reply_text(
            "❌ Game ID / Zone ID မမှန်ဘူး။ တစ်ခါတည်း ပြန်ပို့ပေးပါ။\n"
            "ဥပမာ: 12345678 (1234)"
        )
        return ASK_IDS
    context.user_data["mlbb_id"] = mlbb_id
    context.user_data["zone_id"] = zone_id
    


    product_name = context.user_data["product_name"]
    price = context.user_data["price"]
    
    await update.message.reply_text(
        f"📋 **Order အကျဉ်းချုပ်**\n"
        f"ပစ္စည်း: {product_name}\n"
        f"Game ID: {mlbb_id} ({zone_id})\n"
        f"စုစုပေါင်း: {fmt_price(price)}\n\n"
        f"💰 **ငွေလွှဲရန်**\n"
        f"နာမည်: {config.PAYMENT_NAME}\n"
        f"KBZPay: {config.PAYMENT_KBZ}\n"
        f"WavePay: {config.PAYMENT_WAVE}\n\n"
        "ငွေလွှဲပြီးရင် **screenshot (ပုံ)** ကို ဒီမှာ ပို့ပေးပါ။ 📸\n"
        "စာနဲ့ ပို့လို့မရဘူး၊ ပုံပဲ ပို့ပါ။",
        parse_mode="Markdown",
    )
    return ASK_PHOTO

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "📸 ငွေလွှဲပြီးတဲ့ screenshot ပုံကို ပို့ပေးပါ။ စာနဲ့ မရဘူးနော်။"
        )
        return ASK_PHOTO
    photo_file_id = update.message.photo[-1].file_id
    photo_bytes = None
    try:
        tg_file = await context.bot.get_file(photo_file_id)
        photo_bytes = bytes(await tg_file.download_as_bytearray())
    except Exception as e:
        logger.error("Screenshot download မရဘူး: %s", e)
    user = update.effective_user
    order_id = next_order_id()
    order = {
        "id": order_id,
        "user_id": user.id,
        "username": user.username or "",
        "product_key": context.user_data["product_key"],
        "product_name": context.user_data["product_name"],
        "mlbb_id": context.user_data["mlbb_id"],
        "zone_id": context.user_data["zone_id"],
        "price": context.user_data["price"],
        "photo_file_id": photo_file_id,
        "photo_blob": photo_bytes,
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_order(order)
    await update.message.reply_text(
        f"✅ Order လက်ခံပြီ!\n\n"
        f"Order ID: {order_id}\n"
        f"ပစ္စည်း: {order['product_name']}\n"
        f"Game ID: {order['mlbb_id']} ({order['zone_id']})\n"
        f"စုစုပေါင်း: {fmt_price(order['price'])}\n"
        f"အခြေအနေ: {STATUS_MY['pending']}\n\n"
        "Admin က ငွေလွှဲ screenshot စစ်ပြီး အတည်ပြုပေးမယ်။\n"
        "ခဏစောင့်ပေးပါနော်။ 🙏\n"
        "အခြေအနေ ကြည့်ချင်ရင် /myorders နှိပ်ပါ။"
    )
    if config.ADMIN_ID:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"admin_confirm_{order_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}"),
                ]
            ]
        )
        caption = (
            f"🆕 **Order အသစ်: {order_id}**\n"
            f"ပစ္စည်း: {order['product_name']}\n"
            f"Game ID: {order['mlbb_id']} ({order['zone_id']})\n"
            f"စုစုပေါင်း: {fmt_price(order['price'])}\n"
            f"ဝယ်သူ: @{(order['username'] or '-').replace('_', '\_')} (ID: {order['user_id']})\n"
            f"အချိန်: {order['created_at']}\n\n"
            "Screenshot အပေါ်မှာ ကြည့်ပါ။ Confirm / Reject ရွေးပါ။"
        )
        try:
            sender = context.application.bot_data.get("admin_bot") or context.bot
            await sender.send_photo(
                chat_id=config.ADMIN_ID,
                photo=photo_bytes if photo_bytes else photo_file_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error("Admin သို့ ပို့မရဘူး: %s", e)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Order ကို ဖျက်လိုက်ပြီ။ အသစ်မှာချင်ရင် /start နှိပ်ပါ။")
    return ConversationHandler.END

async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders = list_orders(user_id=user_id, limit=5)
    if not orders:
        text = "📦 မင်း order မရှိသေးဘူး။ /start နဲ့ မှာလိုက်ပါ။"
    else:
        lines = ["📦 **ငါ့ order တွေ**\n"]
        for o in orders:
            lines.append(
                f"• {o['id']} — {o['product_name']} — {fmt_price(o['price'])} — "
                f"{STATUS_MY.get(o['status'], o['status'])}"
            )
        text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

async def myorders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_my_orders(update, context)

def is_admin(user_id):
    return config.ADMIN_ID and user_id == config.ADMIN_ID

def customer_bot(context):
    return context.application.bot_data.get("store_bot", context.bot)


async def edit_admin_message(query, text):
    try:
        await query.edit_message_caption(caption=text)
    except Exception:
        await query.edit_message_text(text=text)


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("ဒီ bot က Admin အတွက်ပဲ ဖြစ်ပါတယ်။")
        return
    await update.message.reply_text(
        "🛠️ **YY MLBB STORE ADMIN**\n\n"
        "Order အသစ်တွေ ဒီ bot ထဲ ရောက်လာမယ်။\n"
        "Screenshot စစ်ပြီး Confirm / Reject နှိပ်ပါ။\n"
        "ထည့်ပေးပြီးရင် /done MLBB-0001 လို့ ပို့ပါ။",
        reply_markup=admin_menu_keyboard(),
        parse_mode="Markdown",
    )


async def admin_orders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("ဒါ Admin အတွက်ပဲ ဖြစ်ပါတယ်။")
        return
    await send_admin_orders(update, context)


async def send_admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    orders = list_orders(status="pending", limit=10)
    if not orders:
        text = "⏳ စောင့်နေတဲ့ order မရှိဘူး။"
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=admin_menu_keyboard())
        else:
            await update.message.reply_text(text, reply_markup=admin_menu_keyboard())
        return
    intro = (
        f"📋 စောင့်နေတဲ့ order {len(orders)} ခု ပို့လိုက်ပြီ။\n"
        "Screenshot ကြည့်ပြီး Confirm / Reject နှိပ်ပါ။"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(intro, reply_markup=admin_menu_keyboard())
    else:
        await update.message.reply_text(intro, reply_markup=admin_menu_keyboard())
    for o in orders:
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Confirm", callback_data=f"admin_confirm_{o['id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{o['id']}"),
            ]]
        )
        caption = (
            f"📋 **Order: {o['id']}**\n"
            f"ပစ္စည်း: {o['product_name']}\n"
            f"Game ID: {o['mlbb_id']} ({o['zone_id']})\n"
            f"စုစုပေါင်း: {fmt_price(o['price'])}\n"
            f"ဝယ်သူ: @{(o['username'] or '-').replace('_', '\_')} (ID: {o['user_id']})\n"
            f"အချိန်: {o['created_at']}\n\n"
            "Screenshot အပေါ်မှာ ကြည့်ပါ။ Confirm / Reject ရွေးပါ။"
        )
        photo = o.get("photo_blob") or o["photo_file_id"]
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as e:
            logger.error("Order photo ပို့မရဘူး: %s", e)
            await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard, parse_mode="Markdown")


async def orders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("ဒီ command က Admin အတွက်ပဲ ဖြစ်ပါတယ်။")
        return
    await send_admin_orders(update, context)

async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("ဒီ command က Admin အတွက်ပဲ ဖြစ်ပါတယ်။")
        return
    if not context.args:
        await update.message.reply_text("သုံးပုံ: /done MLBB-0001")
        return
    order_id = context.args[0].strip().upper()
    order = get_order(order_id)
    if not order:
        await update.message.reply_text(f"Order {order_id} ကို ရှာမတွေ့ဘူး။")
        return
    update_status(order_id, "done")
    await update.message.reply_text(f"🎉 Order {order_id} ပြီးသွားပြီလို့ မှတ်လိုက်ပြီ။")
    try:
        await customer_bot(context).send_message(
            chat_id=order["user_id"],
            text=(
                f"🎉 Order {order_id} ပြီးသွားပြီ!\n"
                f"{order['product_name']} ကို မင်း အကောင့် {order['mlbb_id']} ({order['zone_id']}) ထဲ ထည့်ပေးပြီးပြီ။\n"
                "ဂိမ်းထဲမှာ စစ်ကြည့်လိုက်ပါ။ ကျေးဇူးတင်ပါတယ်! 🙏"
            ),
        )
    except Exception as e:
        logger.error("Customer သို့ done အကြောင်းကြားမရဘူး: %s", e)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await edit_admin_message(query, "ဒါ Admin အတွက်ပဲ ဖြစ်ပါတယ်။")
        return
    data = query.data
    if data.startswith("admin_confirm_"):
        order_id = data.replace("admin_confirm_", "", 1)
        new_status = "confirmed"
        action_my = "✅ ငွေအတည်ပြုလိုက်ပြီ"
    elif data.startswith("admin_reject_"):
        order_id = data.replace("admin_reject_", "", 1)
        new_status = "rejected"
        action_my = "❌ ပယ်လိုက်ပြီ"
    else:
        return
    order = get_order(order_id)
    if not order:
        await edit_admin_message(query, f"Order {order_id} ကို ရှာမတွေ့ဘူး။")
        return
    update_status(order_id, new_status)
    old_caption = query.message.caption or query.message.text or ""
    await edit_admin_message(query, f"{old_caption}\n\n{action_my} — {STATUS_MY[new_status]}")
    if new_status == "confirmed":
        msg = "Done✅"
    else:
        msg = (
            f"❌ Order {order_id} — ပယ်ချခံရတယ်။\n"
            "ငွေလွှဲ screenshot / ID မှားနေလို့ဖြစ်နိုင်တယ်။\n"
            "Admin ကို ပြန်ဆက်သွယ်ပါ၊ ဒါမှမဟုတ် /start နဲ့ အသစ်ပြန်မှာပါ။"
        )
    try:
        await customer_bot(context).send_message(chat_id=order["user_id"], text=msg)
    except Exception as e:
        logger.error("Customer သို့ အကြောင်းကြားမရဘူး: %s", e)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **MLBB Top-Up Bot အသုံးပြုနည်း**\n\n"
        "/start — စျေးနှုန်း ကြည့်ပြီး မှာမယ်\n"
        "/myorders — ငါ့ order အခြေအနေ ကြည့်မယ်\n"
        "/cancel — မှာနေတာ ဖျက်မယ်\n\n"
        "Admin bot မှာ:\n"
        "/orders — စောင့်နေတဲ့ order တွေ\n"
        "/done MLBB-0001 — order ပြီးသွားပြီလို့ မှတ်မယ်\n\n"
        "⚠️ Order တိုင်းမှာ Game ID + Zone ID + ငွေလွှဲ screenshot ပုံ — ၃ ခု လုံးရှိရမယ်။",
        parse_mode="Markdown",
    )

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("ဒီ bot က Admin တစ်ယောက်တည်းအတွက်ပဲ ဖြစ်ပါတယ်။")
        return
    await update.message.reply_text(
        "🛠️ **Admin Bot အသုံးပြုနည်း**\n\n"
        "/start — Admin menu\n"
        "/orders — စောင့်နေတဲ့ order တွေ\n"
        "/done MLBB-0001 — order ပြီးသွားပြီလို့ မှတ်မယ်\n\n"
        "Order အသစ်ရောက်ရင် Screenshot ကြည့်ပြီး Confirm / Reject နှိပ်ပါ။",
        reply_markup=admin_menu_keyboard(),
        parse_mode="Markdown",
    )


async def run_apps(store_app, admin_app):
    await store_app.initialize()
    await store_app.start()
    await store_app.updater.start_polling()
    if admin_app:
        await admin_app.initialize()
        await admin_app.start()
        await admin_app.updater.start_polling()
    print("🤖 Bot တွေ စတင်နေပြီ...")
    await asyncio.Event().wait()


def main():
    init_db()
    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN မရှိဘူး။ .env ထဲ BOT_TOKEN=... ထည့်ပါ။")
        return
    if not config.ADMIN_ID:
        print("⚠️ ADMIN_ID မရှိဘူး။ Admin က order လက်ခံရမှာ မဟုတ်ဘူး။ .env ထဲ ADMIN_ID=... ထည့်ပါ။")
    if not config.ADMIN_BOT_TOKEN:
        print("⚠️ ADMIN_BOT_TOKEN မရှိဘူး။ Order တွေကို store bot ကနေပဲ ပို့မယ်။")
    store_app = Application.builder().token(config.BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(select_product, pattern=r"^(cat_|product_|back_menu|my_orders)")],
            ASK_IDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_ids)],
            
            ASK_PHOTO: [MessageHandler(filters.PHOTO, ask_photo), MessageHandler(filters.TEXT & ~filters.COMMAND, ask_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    store_app.add_handler(conv)
    store_app.add_handler(CommandHandler("myorders", myorders_cmd))
    store_app.add_handler(CommandHandler("help", help_cmd))
    admin_app = None
    if config.ADMIN_BOT_TOKEN:
        admin_app = Application.builder().token(config.ADMIN_BOT_TOKEN).build()
        admin_app.add_handler(CommandHandler("start", admin_start))
        admin_app.add_handler(CommandHandler("orders", orders_cmd))
        admin_app.add_handler(CommandHandler("done", done_cmd))
        admin_app.add_handler(CommandHandler("help", admin_help))
        admin_app.add_handler(CallbackQueryHandler(admin_orders_callback, pattern=r"^admin_orders$"))
        admin_app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_(confirm|reject)_"))
        store_app.bot_data["admin_bot"] = admin_app.bot
        admin_app.bot_data["store_bot"] = store_app.bot
    else:
        store_app.add_handler(CommandHandler("orders", orders_cmd))
        store_app.add_handler(CommandHandler("done", done_cmd))
        store_app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_(confirm|reject)_"))
    asyncio.run(run_apps(store_app, admin_app))

if __name__ == "__main__":
    main()
