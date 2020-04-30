import html
from typing import List

from telegram import Bot, Chat, Update, ParseMode
from telegram.error import BadRequest, Unauthorized
from telegram.ext import CommandHandler, RegexHandler, Filters, run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, LOGGER, SUDO_USERS, TIGER_USERS
from tg_bot.modules.helper_funcs.chat_status import user_not_admin, user_admin
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import requesting_sql as sql

REQUEST_GROUP = 5
REQUEST_IMMUNE_USERS = SUDO_USERS + TIGER_USERS


@run_async
@user_admin
def request(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat
    msg = update.effective_message

    if chat.type == chat.PRIVATE:
        if len(args) >= 1:
            if args[0] in ("yes", "on"):
                sql.set_user_setting(chat.id, True)
                msg.reply_text("Turned on requesting! You'll be notified whenever anyone requests something.")

            elif args[0] in ("no", "off"):
                sql.set_user_setting(chat.id, False)
                msg.reply_text("Turned off requesting! You wont get any requests.")
        else:
            msg.reply_text(f"Your current request preference is: `{sql.user_should_request(chat.id)}`",
                           parse_mode=ParseMode.MARKDOWN)

    else:
        if len(args) >= 1:
            if args[0] in ("yes", "on"):
                sql.set_chat_setting(chat.id, True)
                msg.reply_text("Turned on requesting! Admins who have turned on requests will be notified when /request "
                               "or @admin are called.")

            elif args[0] in ("no", "off"):
                sql.set_chat_setting(chat.id, False)
                msg.reply_text("Turned off requesting! No admins will be notified on /request or @admin.")
        else:
            msg.reply_text(f"This chat's current setting is: `{sql.chat_should_request(chat.id)}`",
                           parse_mode=ParseMode.MARKDOWN)


@run_async
@user_not_admin
@loggable
def request(bot: Bot, update: Update) -> str:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat and message.reply_to_message and sql.chat_should_request(chat.id):

        requested = message.reply_to_message.from_user
        chat_name = chat.title or chat.first or chat.username
        admin_list = chat.get_administrators()
        message = update.effective_message

        if user.id == requested.id:
            message.reply_text("Uh yeah, Sure.")
            return ""

        if user.id == bot.id:
            message.reply_text("Nice try.")
            return ""

        if requested.id in REQUEST_IMMUNE_USERS:
            message.reply_text("Uh? You requesting whitelisted users?")
            return ""

        if chat.username and chat.type == Chat.SUPERGROUP:

            reported = f"{mention_html(user.id, user.first_name)} requested {mention_html(requested.id, requested.first_name)} to the admins!"

            msg = (f"<b>{html.escape(chat.title)}:</b>\n"
                   f"<b>Requested user:</b> {mention_html(reported_user.id, requested.first_name)} (<code>{requested.id}</code>)\n"
                   f"<b>Requested by:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)")
            link = f'\n<b>Link:</b> <a href="https://t.me/{chat.username}/{message.message_id}">click here</a>'

            should_forward = False
        else:
            reported = f"{mention_html(user.id, user.first_name)} requested " \
                       f"{mention_html(requested.id, requested.first_name)} to the admins!"

            msg = f'{mention_html(user.id, user.first_name)} is calling for admins in "{html.escape(chat_name)}"!'
            link = ""
            should_forward = True

        message.reply_text(requested, parse_mode=ParseMode.HTML)

        for admin in admin_list:

            if admin.user.is_bot:  # can't message bots
                continue

            if sql.user_should_request(admin.user.id):

                try:
                    bot.send_message(admin.user.id, msg + link, parse_mode=ParseMode.HTML)

                    if should_forward:
                        message.reply_to_message.forward(admin.user.id)

                        if len(message.text.split()) > 1:  # If user is giving a reason, send his message too
                            message.forward(admin.user.id)

                except Unauthorized:
                    pass

                except BadRequest:  # TODO: cleanup exceptions
                    LOGGER.exception("Exception while requesting user")

        return msg

    return ""


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return "This chat is setup to send user request to admins, via /request and @admin: `{}`".format(
        sql.chat_should_request(chat_id))


def __user_settings__(user_id):
    return "You receive request from chats you're admin in: `{}`.\nToggle this with /requests in PM.".format(
        sql.user_should_request(user_id))


__help__ = """
 - /request <request name>: reply to a message to report it to admins.
 - @admin: reply to a message to report it to admins.
NOTE: Neither of these will get triggered if used by admins.

*Admin only:*
 - /Requests <on/off>: change report setting, or view current status.
   - If done in pm, toggles your status.
   - If in chat, toggles that chat's status.
"""

SETTING_HANDLER = CommandHandler("requests", request_setting, pass_args=True)
REQUEST_HANDLER = CommandHandler("request", request, filters=Filters.group)
ADMIN_REQUEST_HANDLER = RegexHandler("(?i)@admin(s)?", request)

dispatcher.add_handler(SETTING_HANDLER)
dispatcher.add_handler(REQUEST_HANDLER, REQUEST_GROUP)
dispatcher.add_handler(ADMIN_REQUEST_HANDLER, REQUEST_GROUP)

__mod_name__ = "Request"
__handlers__ = [(REQUEST_HANDLER, REQUEST_GROUP), (ADMIN_REQUEST_HANDLER, REQUEST_GROUP), (SETTING_HANDLER)]
