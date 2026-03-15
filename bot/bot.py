"""
Openclaw Telegram Bot
---------------------
Runs as a long-polling client — outbound to api.telegram.org only.
No inbound ports. No access to internal_net services.

Sends authorized users a button that opens the Mini App (hosted on HTTPS).
The Mini App then calls the Nginx gateway directly on the LAN.
"""
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ["BOT_TOKEN"]
MINI_APP_URL = os.environ["MINI_APP_URL"]

ALLOWED_USER_IDS: set[int] = set(
    int(uid.strip())
    for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
)


def allowed(user_id: int) -> bool:
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not allowed(user.id):
        logger.warning("Blocked unauthorized user %s (%s)", user.id, user.username)
        await update.message.reply_text("Access denied.")
        return

    keyboard = [[
        InlineKeyboardButton(
            text="Open Openclaw Terminal",
            web_app=WebAppInfo(url=MINI_APP_URL),
        )
    ]]
    await update.message.reply_text(
        f"Openclaw link established, {user.first_name}.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently block non-command messages from unauthorized users."""
    user = update.effective_user
    if user and not allowed(user.id):
        await update.message.reply_text("Access denied.")


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handle_message)
    )
    logger.info("Bot started — long-polling (outbound only)")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
