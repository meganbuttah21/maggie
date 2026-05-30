import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
db = Database()

# Conversation states
(
    ADD_PHOTOS, ADD_COMPLEX, ADD_TYPE, ADD_ROOMS, ADD_AREA,
    ADD_PRICE, ADD_SOURCE, ADD_DESCRIPTION, ADD_CONFIRM,
    SEARCH_TYPE, SEARCH_ROOMS, SEARCH_MAX_PRICE
) = range(12)

ROOM_TYPES = ["Студия", "1+1", "2+1", "3+1", "4+1"]
SOURCES = ["Наш объект", "Брокер"]

# ─── HELPERS ───────────────────────────────────────────────

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить объект", callback_data="add")],
        [InlineKeyboardButton("🔍 Найти объект", callback_data="search")],
        [InlineKeyboardButton("📋 Все объекты", callback_data="list_all")],
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])

def format_card(prop):
    source_emoji = "🏠" if prop["source"] == "Наш объект" else "🤝"
    lines = [
        f"🏢 *{prop['complex_name']}*",
        f"🛏 {prop['room_type']} · 📐 {prop['area']} м²",
        f"💰 {int(prop['price']):,} $".replace(",", " "),
        f"{source_emoji} {prop['source']}",
    ]
    if prop.get("description"):
        lines.append(f"\n📝 {prop['description']}")
    lines.append(f"\n🆔 ID: {prop['id']}")
    return "\n".join(lines)

# ─── START ─────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = "👋 Привет! Это твой каталог недвижимости.\nВыбери действие:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())

# ─── ADD FLOW ──────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["new_prop"] = {"photos": []}
    await query.edit_message_text(
        "📸 Отправь фотографии объекта (можно несколько).\nКогда закончишь — нажми кнопку ниже.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Фото загружены", callback_data="photos_done")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ])
    )
    return ADD_PHOTOS

async def receive_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data["new_prop"]["photos"].append(photo.file_id)
    await update.message.reply_text(
        f"✅ Фото {len(context.user_data['new_prop']['photos'])} добавлено. Отправь ещё или нажми «Фото загружены».",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Фото загружены", callback_data="photos_done")],
        ])
    )
    return ADD_PHOTOS

async def photos_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    photos = context.user_data["new_prop"].get("photos", [])
    if not photos:
        await query.edit_message_text(
            "⚠️ Добавь хотя бы одно фото!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ])
        )
        return ADD_PHOTOS
    await query.edit_message_text("🏢 Введи название жилого комплекса:", reply_markup=cancel_keyboard())
    return ADD_COMPLEX

async def add_complex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prop"]["complex_name"] = update.message.text.strip()
    buttons = [[InlineKeyboardButton(t, callback_data=f"type_{t}")] for t in ROOM_TYPES]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    await update.message.reply_text("🛏 Выбери тип:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADD_TYPE

async def add_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    room_type = query.data.replace("type_", "")
    context.user_data["new_prop"]["room_type"] = room_type
    await query.edit_message_text("📐 Введи площадь в м² (например: 45.5):", reply_markup=cancel_keyboard())
    return ADD_AREA

async def add_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        area = float(update.message.text.replace(",", "."))
        context.user_data["new_prop"]["area"] = area
    except ValueError:
        await update.message.reply_text("⚠️ Введи число, например: 45.5")
        return ADD_AREA
    await update.message.reply_text("💰 Введи цену в $ (например: 85000):", reply_markup=cancel_keyboard())
    return ADD_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(" ", "").replace(",", ""))
        context.user_data["new_prop"]["price"] = price
    except ValueError:
        await update.message.reply_text("⚠️ Введи число, например: 85000")
        return ADD_PRICE
    buttons = [[InlineKeyboardButton(s, callback_data=f"src_{s}")] for s in SOURCES]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    await update.message.reply_text("🏠 Чей объект?", reply_markup=InlineKeyboardMarkup(buttons))
    return ADD_SOURCE

async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    source = query.data.replace("src_", "")
    context.user_data["new_prop"]["source"] = source
    await query.edit_message_text(
        "📝 Добавь описание (или нажми «Пропустить»):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_desc")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ])
    )
    return ADD_DESCRIPTION

async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prop"]["description"] = update.message.text.strip()
    return await show_confirm(update, context)

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["new_prop"]["description"] = ""
    return await show_confirm(update, context, query=query)

async def show_confirm(update, context, query=None):
    prop = context.user_data["new_prop"]
    preview = (
        f"📋 *Проверь данные:*\n\n"
        f"🏢 Комплекс: {prop['complex_name']}\n"
        f"🛏 Тип: {prop['room_type']}\n"
        f"📐 Площадь: {prop['area']} м²\n"
        f"💰 Цена: {int(prop['price']):,} $".replace(",", " ") + "\n"
        f"📸 Фото: {len(prop['photos'])} шт.\n"
        f"🏠 Источник: {prop['source']}\n"
        + (f"📝 {prop['description']}" if prop.get('description') else "")
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Сохранить", callback_data="confirm_save")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ])
    if query:
        await query.edit_message_text(preview, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(preview, reply_markup=kb, parse_mode="Markdown")
    return ADD_CONFIRM

async def confirm_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prop = context.user_data["new_prop"]
    prop_id = db.add_property(
        complex_name=prop["complex_name"],
        room_type=prop["room_type"],
        area=prop["area"],
        price=prop["price"],
        source=prop["source"],
        description=prop.get("description", ""),
        photos=prop["photos"],
    )
    await query.edit_message_text(
        f"✅ Объект #{prop_id} сохранён!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="menu")]])
    )
    context.user_data.clear()
    return ConversationHandler.END

# ─── SEARCH FLOW ───────────────────────────────────────────

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["search"] = {}
    buttons = [[InlineKeyboardButton(t, callback_data=f"stype_{t}")] for t in ROOM_TYPES]
    buttons.append([InlineKeyboardButton("🔍 Любой тип", callback_data="stype_any")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    await query.edit_message_text("🛏 Тип квартиры:", reply_markup=InlineKeyboardMarkup(buttons))
    return SEARCH_TYPE

async def search_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    val = query.data.replace("stype_", "")
    context.user_data["search"]["room_type"] = None if val == "any" else val
    buttons = [
        [InlineKeyboardButton("Наш объект", callback_data="ssrc_our"),
         InlineKeyboardButton("Брокер", callback_data="ssrc_broker")],
        [InlineKeyboardButton("🔍 Любой", callback_data="ssrc_any")],
    ]
    await query.edit_message_text("🏠 Источник:", reply_markup=InlineKeyboardMarkup(buttons))
    return SEARCH_ROOMS

async def search_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mapping = {"ssrc_our": "Наш объект", "ssrc_broker": "Брокер", "ssrc_any": None}
    context.user_data["search"]["source"] = mapping.get(query.data)
    await query.edit_message_text("💰 Максимальная цена $ (или напиши 0 — без ограничений):")
    return SEARCH_MAX_PRICE

async def search_max_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(" ", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("⚠️ Введи число")
        return SEARCH_MAX_PRICE

    filters = context.user_data["search"]
    filters["max_price"] = None if val == 0 else val

    results = db.search(
        room_type=filters.get("room_type"),
        source=filters.get("source"),
        max_price=filters.get("max_price"),
    )

    if not results:
        await update.message.reply_text(
            "😔 Ничего не найдено по этим фильтрам.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="menu")]])
        )
        return ConversationHandler.END

    await update.message.reply_text(f"✅ Найдено: {len(results)} объект(ов)")
    for prop in results[:10]:
        await send_property_card(update, context, prop)

    if len(results) > 10:
        await update.message.reply_text(f"...и ещё {len(results) - 10}. Уточни фильтры для точного поиска.")

    await update.message.reply_text(
        "Что дальше?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Новый поиск", callback_data="search")],
            [InlineKeyboardButton("🏠 В меню", callback_data="menu")],
        ])
    )
    return ConversationHandler.END

async def send_property_card(update, context, prop):
    caption = format_card(prop)
    photos = prop.get("photos", [])
    chat_id = update.effective_chat.id

    if not photos:
        await context.bot.send_message(chat_id, caption, parse_mode="Markdown")
        return

    if len(photos) == 1:
        await context.bot.send_photo(chat_id, photos[0], caption=caption, parse_mode="Markdown")
    else:
        media = [InputMediaPhoto(photos[0], caption=caption, parse_mode="Markdown")]
        for fid in photos[1:9]:
            media.append(InputMediaPhoto(fid))
        await context.bot.send_media_group(chat_id, media)

# ─── LIST ALL ──────────────────────────────────────────────

async def list_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    results = db.get_all()
    if not results:
        await query.edit_message_text(
            "📭 Каталог пуст. Добавь первый объект!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="menu")]])
        )
        return
    await query.edit_message_text(f"📋 Всего объектов: {len(results)}")
    for prop in results[:10]:
        await send_property_card(update, context, prop)
    if len(results) > 10:
        await context.bot.send_message(
            update.effective_chat.id,
            f"...показано 10 из {len(results)}. Используй поиск для фильтрации.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Поиск", callback_data="search")]])
        )

# ─── CANCEL / MENU ─────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Отменено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="menu")]]))
    else:
        await update.message.reply_text("❌ Отменено.", reply_markup=main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ─── MAIN ──────────────────────────────────────────────────

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не задан!")

    app = Application.builder().token(TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_start, pattern="^add$")],
        states={
            ADD_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photos),
                CallbackQueryHandler(photos_done, pattern="^photos_done$"),
            ],
            ADD_COMPLEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_complex)],
            ADD_TYPE: [CallbackQueryHandler(add_type, pattern="^type_")],
            ADD_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_area)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_SOURCE: [CallbackQueryHandler(add_source, pattern="^src_")],
            ADD_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_description),
                CallbackQueryHandler(skip_description, pattern="^skip_desc$"),
            ],
            ADD_CONFIRM: [CallbackQueryHandler(confirm_save, pattern="^confirm_save$")],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
        allow_reentry=True,
    )

    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^search$")],
        states={
            SEARCH_TYPE: [CallbackQueryHandler(search_type, pattern="^stype_")],
            SEARCH_ROOMS: [CallbackQueryHandler(search_source, pattern="^ssrc_")],
            SEARCH_MAX_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_max_price)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv)
    app.add_handler(search_conv)
    app.add_handler(CallbackQueryHandler(list_all, pattern="^list_all$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu$"))

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
