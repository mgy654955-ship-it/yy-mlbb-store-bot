# bot.py — MLBB Top-Up Bot (Manual Order ONLY)
import logging
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

SELECT_PRODUCT, ASK_ID, ASK_ZONE, ASK_PHOTO = range(4)

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
            created_at TEXT
        )
        """
    )
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
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            [InlineKeyboardButton("💎 Diamond ဝယ်မယ်", callback_data="cat_diamond")],
            [InlineKeyboardButton("🎫 Weekly Pass ဝယ်မယ်", callback_data="cat_weekly")],
            [InlineKeyboardButton("📦 ငါ့ order တွေ", callback_data="my_orders")],
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
    lines = ["🛒 **MLBB Top-Up — စျေးနှုန်း**\n"]
    lines.append("💎 **Diamond**")
    for key in config.DIAMOND_KEYS:
        p = config.PRODUCTS[key]
        lines.append(f"• {p['name']} — {fmt_price(p['price'])}")
    lines.append("\n🎫 **Weekly Pass** (1 ခု = 220 Diamond, 7 ရက်)")
    for key in config.WEEKLY_KEYS:
        p = config.PRODUCTS[key]
        lines.append(f"• {p['name']} — {fmt_price(p['price'])}")
    lines.append("\nဝယ်ချင်တာကို ရွေးလိုက်ပါ။ 👇")
    return "\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = (
        "မင်္ဂလာပါ! 👋\n"
        "MLBB Diamond / Weekly Pass ဝယ်လို့ရတဲ့ ဆိုင်ပါ။\n\n"
        + price_list_text()
    )
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
            "💎 Diamond — ဘယ်လောက် ဝယ်မလဲ?", reply_markup=product_keyboard(config.DIAMOND_KEYS)
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
        context.user_data["product_key"] = key
        context.user_data["product_name"] = product["name"]
        context.user_data["price"] = product["price"]
        await query.edit_message_text(
            f"ရွေးလိုက်ပြီ: {product['name']} — {fmt_price(product['price'])}\n\n"
            "🔢 မင်း MLBB ID ကို ပို့ပေးပါ။\n"
            "(ဂိမ်းထဲက Profile မှာ ကြည့်လို့ရတယ်။ နံပါတ်သက်သက် ပို့ပါ။\n"
            "ဥပမာ: 12345678)"
        )
        return ASK_ID
    return SELECT_PRODUCT

async def ask_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    clean = text.replace(" ", "")
    if not clean.isdigit() or len(clean) < 5:
        await update.message.reply_text(
            "❌ MLBB ID မမှန်ဘူး။ နံပါတ်သက်သက် ပြန်ပို့ပေးပါ။\nဥပမာ: 12345678"
        )
        return ASK_ID
    context.user_data["mlbb_id"] = clean
    await update.message.reply_text(
        "✅ MLBB ID ရပြီ။\n\n"
        "🌐 အခု Zone / Server ID ကို ပို့ပေးပါ။\n"
        "(MLBB ID နောက်က ကွင်းထဲက နံပါတ်။ ဥပမာ: 1234)"
    )
    return ASK_ZONE

async def ask_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    clean = text.replace(" ", "").replace("(", "").replace(")", "")
    if not clean.isdigit() or len(clean) < 3:
        await update.message.reply_text(
            "❌ Zone ID မမှန်ဘူး။ နံပါတ်သက်သက် ပြန်ပို့ပေးပါ။\nဥပမာ: 1234"
        )
        return ASK_ZONE
    context.user_data["zone_id"] = clean
    product_name = context.user_data["product_name"]
    price = context.user_data["price"]
    mlbb_id = context.user_data["mlbb_id"]
    await update.message.reply_text(
        f"📋 **Order အကျဉ်းချုပ်**\n"
        f"ပစ္စည်း: {product_name}\n"
        f"MLBB ID: {mlbb_id} ({clean})\n"
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
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_order(order)
    await update.message.reply_text(
        f"✅ Order လက်ခံပြီ!\n\n"
        f"Order ID: {order_id}\n"
        f"ပစ္စည်း: {order['product_name']}\n"
        f"MLBB ID: {order['mlbb_id']} ({order['zone_id']})\n"
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
            f"MLBB ID: {order['mlbb_id']} ({order['zone_id']})\n"
            f"စုစုပေါင်း: {fmt_price(order['price'])}\n"
            f"ဝယ်သူ: @{order['username'] or '-'} (ID: {order['user_id']})\n"
            f"အချိန်: {order['created_at']}\n\n"
            "Screenshot အပေါ်မှာ ကြည့်ပါ။ Confirm / Reject ရွေးပါ။"
        )
        try:
            await context.bot.send_photo(
                chat_id=config.ADMIN_ID,
                photo=photo_file_id,
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

async def orders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("ဒီ command က Admin အတွက်ပဲ ဖြစ်ပါတယ်။")
        return
    orders = list_orders(status="pending", limit=10)
    if not orders:
        await update.message.reply_text("⏳ စောင့်နေတဲ့ order မရှိဘူး။")
        return
    lines = ["📋 **စောင့်နေတဲ့ order တွေ**\n"]
    for o in orders:
        lines.append(
            f"• {o['id']} — {o['product_name']} — {fmt_price(o['price'])}\n"
            f"  MLBB: {o['mlbb_id']} ({o['zone_id']}) — @{o['username'] or '-'}"
        )
    lines.append("\nပြီးသွားရင် /done MLBB-0001 လို့ ပို့ပါ။")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

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
        await context.bot.send_message(
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
        await query.edit_message_caption(caption="ဒါ Admin အတွက်ပဲ ဖြစ်ပါတယ်။")
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
        await query.edit_message_caption(caption=f"Order {order_id} ကို ရှာမတွေ့ဘူး။")
        return
    update_status(order_id, new_status)
    old_caption = query.message.caption or ""
    await query.edit_message_caption(
        caption=f"{old_caption}\n\n{action_my} — {STATUS_MY[new_status]}"
    )
    if new_status == "confirmed":
        msg = (
            f"✅ Order {order_id} — ငွေအတည်ပြုပြီ!\n"
            f"{order['product_name']} ကို မင်း အကောင့် {order['mlbb_id']} ({order['zone_id']}) ထဲ "
            "ထည့်ပေးတော့မယ်။ ခဏစောင့်ပေးပါနော်။ 🙏"
        )
    else:
        msg = (
            f"❌ Order {order_id} — ပယ်ချခံရတယ်။\n"
            "ငွေလွှဲ screenshot / ID မှားနေလို့ဖြစ်နိုင်တယ်။\n"
            "Admin ကို ပြန်ဆက်သွယ်ပါ၊ ဒါမှမဟုတ် /start နဲ့ အသစ်ပြန်မှာပါ။"
        )
    try:
        await context.bot.send_message(chat_id=order["user_id"], text=msg)
    except Exception as e:
        logger.error("Customer သို့ အကြောင်းကြားမရဘူး: %s", e)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **MLBB Top-Up Bot အသုံးပြုနည်း**\n\n"
        "/start — စျေးနှုန်း ကြည့်ပြီး မှာမယ်\n"
        "/myorders — ငါ့ order အခြေအနေ ကြည့်မယ်\n"
        "/cancel — မှာနေတာ ဖျက်မယ်\n\n"
        "Admin:\n"
        "/orders — စောင့်နေတဲ့ order တွေ\n"
        "/done MLBB-0001 — order ပြီးသွားပြီလို့ မှတ်မယ်\n\n"
        "⚠️ Order တိုင်းမှာ MLBB ID + Zone ID + ငွေလွှဲ screenshot ပုံ — ၃ ခု လုံးရှိရမယ်။",
        parse_mode="Markdown",
    )

def main():
    init_db()
    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN မရှိဘူး။ .env ထဲ BOT_TOKEN=... ထည့်ပါ။")
        return
    if not config.ADMIN_ID:
        print("⚠️ ADMIN_ID မရှိဘူး။ Admin က order လက်ခံရမှာ မဟုတ်ဘူး။ .env ထဲ ADMIN_ID=... ထည့်ပါ။")
    app = Application.builder().token(config.BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_PRODUCT: [
                CallbackQueryHandler(select_product, pattern=r"^(cat_|product_|back_menu|my_orders)"),
            ],
            ASK_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_id)],
            ASK_ZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_zone)],
            ASK_PHOTO: [
                MessageHandler(filters.PHOTO, ask_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("myorders", myorders_cmd))
    app.add_handler(CommandHandler("orders", orders_cmd))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_(confirm|reject)_"))
    print("🤖 Bot စတင်နေပြီ... (Ctrl+C နဲ့ ရပ်လို့ရတယ်)")
    app.run_polling()

if __name__ == "__main__":
    main()
