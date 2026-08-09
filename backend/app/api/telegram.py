import re
from html import escape
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user_settings import UserSettings
from app.services.devsbite import (
    DevsbiteApiError,
    DevsbiteConfigError,
    DevsbiteRequestError,
    get_combined_analysis,
    get_pairs,
    get_quote,
)
from app.services.pocket_option import (
    PocketOptionApiError,
    PocketOptionConfigError,
    PocketOptionRequestError,
    get_user_info,
)

router = APIRouter()

SUPPORTED_LANGUAGES = {"ru", "en", "es", "pt", "tr", "ar"}
FUNNEL_LANGUAGES = {"ru", "en"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FUNNEL_NODE_PHOTOS = {
    "BOT-01": PROJECT_ROOT / "images" / "bot-start.png",
}
PREMIUM_EMOJI = {
    "wave": '<tg-emoji emoji-id="5321095945780209338">\U0001f44b</tg-emoji>',
    "tool": '<tg-emoji emoji-id="5462921117423384478">\U0001f6e0</tg-emoji>',
    "warning": '<tg-emoji emoji-id="5958289678837746828">\u26a0\ufe0f</tg-emoji>',
    "rocket": '<tg-emoji emoji-id="5188481279963715781">\U0001f680</tg-emoji>',
    "money": '<tg-emoji emoji-id="5417924076503062111">\U0001f4b0</tg-emoji>',
    "pick": '<tg-emoji emoji-id="5197371802136892976">\u26cf\ufe0f</tg-emoji>',
    "chart": '<tg-emoji emoji-id="5298614648138919107">\U0001f4c8</tg-emoji>',
}
START_DEEP_LINKS = {
    "want_bot": ("BOT", None),
    "want_team": ("TEAM", None),
    "want_bot_ru": ("BOT", "ru"),
    "want_bot_en": ("BOT", "en"),
    "want_team_ru": ("TEAM", "ru"),
    "want_team_en": ("TEAM", "en"),
    "bot_ru": ("BOT", "ru"),
    "bot_en": ("BOT", "en"),
    "team_ru": ("TEAM", "ru"),
    "team_en": ("TEAM", "en"),
}
FUNNEL_BUTTON_TEXTS = {
    "ru": {
        "want_bot": "\U0001f525 \u0425\u041e\u0427\u0423 \u0411\u041e\u0422\u0410",
        "want_team": "\U0001f525 \u0425\u041e\u0427\u0423 \u0412 \u041a\u041e\u041c\u0410\u041d\u0414\u0423",
        "ref_ru": "\U0001f1f7\U0001f1fa \u041e\u0422\u041a\u0420\u042b\u0422\u042c \u0410\u041a\u041a\u0410\u0423\u041d\u0422 \u0414\u041b\u042f \u0420\u041e\u0421\u0421\u0418\u0418",
        "ref_world": "\U0001f30d \u041e\u0422\u041a\u0420\u042b\u0422\u042c \u0410\u041a\u041a\u0410\u0423\u041d\u0422 \u0414\u041b\u042f \u0414\u0420\u0423\u0413\u0418\u0425 \u0421\u0422\u0420\u0410\u041d",
        "existing_account": "\U0001f511 \u0423 \u041c\u0415\u041d\u042f \u0423\u0416\u0415 \u0415\u0421\u0422\u042c \u0410\u041a\u041a\u0410\u0423\u041d\u0422",
        "check_topup": "\U0001f525 \u041f\u0420\u041e\u0412\u0415\u0420\u0418\u0422\u042c \u041f\u041e\u041f\u041e\u041b\u041d\u0415\u041d\u0418\u0415",
        "open_bot": "\U0001f916 \u041e\u0422\u041a\u0420\u042b\u0422\u042c PARADOX BOT",
        "join_team": "\U0001f525 \u0412\u041e\u0419\u0422\u0418 \u0412 \u041a\u041e\u041c\u0410\u041d\u0414\u0423",
        "callback_ok": "\u0413\u043e\u0442\u043e\u0432\u043e",
        "topup_pending": "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0443 \u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u043c \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u043c \u0448\u0430\u0433\u043e\u043c.",
    },
    "en": {
        "want_bot": "\U0001f525 I WANT THE BOT",
        "want_team": "\U0001f525 I WANT TO JOIN THE TEAM",
        "ref_ru": "\U0001f1f7\U0001f1fa OPEN ACCOUNT FOR RUSSIA",
        "ref_world": "\U0001f30d OPEN ACCOUNT FOR OTHER COUNTRIES",
        "existing_account": "\U0001f511 I ALREADY HAVE AN ACCOUNT",
        "check_topup": "\U0001f525 CHECK DEPOSIT",
        "open_bot": "\U0001f916 OPEN PARADOX BOT",
        "join_team": "\U0001f525 JOIN THE TEAM",
        "callback_ok": "Done",
        "topup_pending": "Deposit verification will be connected in the next step.",
    },
}
FUNNEL_NODE_TEXTS = {
    "BOT-01": {
        "ru": (
            f"<b><i>\u041f\u0440\u0438\u0432\u0435\u0442, {{name}}</i></b> {PREMIUM_EMOJI['wave']}\n\n"
            "<i>\u0423\u0432\u044b, \u0432 \u0442\u0440\u0435\u0439\u0434\u0438\u043d\u0433\u0435 \u043d\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u0435\u0442 \u043a\u043d\u043e\u043f\u043a\u0438, \u043a\u043e\u0442\u043e\u0440\u0430\u044f \u043d\u0430\u0436\u0438\u043c\u0430\u0435\u0442\u0441\u044f "
            "\u043e\u0434\u0438\u043d \u0440\u0430\u0437 \u0438 \u043d\u0430\u0447\u0438\u043d\u0430\u0435\u0442 \u0437\u0430\u0440\u0430\u0431\u0430\u0442\u044b\u0432\u0430\u0442\u044c \u0432\u043c\u0435\u0441\u0442\u043e \u0442\u0435\u0431\u044f.</i>\n\n"
            f"{PREMIUM_EMOJI['tool']} <i>\u0414\u0430\u0436\u0435 <b>\u0441\u0430\u043c\u044b\u0439 \u0441\u0438\u043b\u044c\u043d\u044b\u0439</b> \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442 \u043e\u0441\u0442\u0430\u0451\u0442\u0441\u044f \u0442\u043e\u043b\u044c\u043a\u043e <b>\u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u043e\u043c</b>.</i>\n\n"
            f"{PREMIUM_EMOJI['warning']} <b>\u041d\u041e!</b> \u041c\u044b \u0441\u043e\u0437\u0434\u0430\u043b\u0438 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442, \u043a\u043e\u0442\u043e\u0440\u044b\u0439 <u>\u043c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u043e \u043e\u0431\u043b\u0435\u0433\u0447\u0438\u0442 \u0442\u0432\u043e\u0439 \u043f\u0443\u0442\u044c</u> "
            "\u043d\u0430 \u043f\u0443\u0442\u0438 \u043a \u0431\u043e\u043b\u044c\u0448\u043e\u043c\u0443 \u0437\u0430\u0440\u0430\u0431\u043e\u0442\u043a\u0443 \u043d\u0430 \u0442\u0440\u0435\u0439\u0434\u0438\u043d\u0433\u0435.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['rocket']} <b>Paradox Bot</b> \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u044f\u0435\u0442 \u0430\u043b\u0433\u043e\u0440\u0438\u0442\u043c\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0430\u043d\u0430\u043b\u0438\u0437 \u0438 "
            "<b>\u0431\u043e\u043b\u0435\u0435 30 \u0438\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440\u043e\u0432</b>, \u0447\u0442\u043e\u0431\u044b \u043f\u043e\u043c\u043e\u0447\u044c \u0442\u0435\u0431\u0435 \u0431\u044b\u0441\u0442\u0440\u0435\u0435 \u043e\u0446\u0435\u043d\u0438\u0432\u0430\u0442\u044c \u0440\u044b\u043d\u043e\u043a, "
            "\u043d\u0430\u0445\u043e\u0434\u0438\u0442\u044c \u0442\u043e\u0440\u0433\u043e\u0432\u044b\u0435 \u0441\u0438\u0442\u0443\u0430\u0446\u0438\u0438 \u0438 \u0434\u0435\u0439\u0441\u0442\u0432\u043e\u0432\u0430\u0442\u044c \u0431\u043e\u043b\u0435\u0435 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u043e.</blockquote>\n\n"
            "<b>\u0412\u0430\u0436\u043d\u043e \u043f\u043e\u043d\u0438\u043c\u0430\u0442\u044c \u0433\u043b\u0430\u0432\u043d\u043e\u0435:</b>\n\n"
            f"{PREMIUM_EMOJI['money']} <i>\u044d\u0442\u043e \u043d\u0435 \u00ab\u043a\u043d\u043e\u043f\u043a\u0430 \u0431\u0430\u0431\u043b\u043e\u00bb</i>\n\n"
            f"{PREMIUM_EMOJI['pick']} <i>\u044d\u0442\u043e \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442, \u0441 \u043a\u043e\u0442\u043e\u0440\u044b\u043c \u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c \u0434\u043e\u043b\u0436\u0435\u043d \u0442\u044b</i>\n\n"
            f"{PREMIUM_EMOJI['chart']} <i>\u0442\u0440\u0435\u0439\u0434\u0438\u043d\u0433 \u2014 \u043d\u0435 \u0431\u044b\u0441\u0442\u0440\u044b\u0439 \u043f\u0440\u0438\u0437, \u0430 \u043f\u0443\u0442\u044c, \u043a\u043e\u0442\u043e\u0440\u044b\u0439 \u0442\u0440\u0435\u0431\u0443\u0435\u0442 "
            "\u0434\u0438\u0441\u0446\u0438\u043f\u043b\u0438\u043d\u044b \u0438 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0438.</i>\n\n"
            "\u041c\u044b \u043d\u0435 \u043e\u0431\u0435\u0449\u0430\u0435\u043c \u043b\u0451\u0433\u043a\u0438\u0445 \u0434\u0435\u043d\u0435\u0433. \u041c\u044b \u0434\u0430\u0451\u043c <b>\u0440\u0430\u0431\u043e\u0447\u0443\u044e \u0441\u0440\u0435\u0434\u0443, "
            "\u0442\u043e\u0440\u0433\u043e\u0432\u043e\u0433\u043e \u0431\u043e\u0442\u0430, \u043f\u043e\u0434\u0440\u043e\u0431\u043d\u044b\u0435 \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438 \u0438 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443</b>, \u0447\u0442\u043e\u0431\u044b "
            "\u0442\u0435\u0431\u0435 \u043d\u0435 \u043f\u0440\u0438\u0448\u043b\u043e\u0441\u044c \u043f\u0440\u043e\u0445\u043e\u0434\u0438\u0442\u044c \u044d\u0442\u043e\u0442 \u043f\u0443\u0442\u044c \u0432 \u043e\u0434\u0438\u043d\u043e\u0447\u043a\u0443.\n\n"
            "<b><i>\u0413\u043e\u0442\u043e\u0432 \u0440\u0430\u0437\u043e\u0431\u0440\u0430\u0442\u044c\u0441\u044f \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0435 \u0438 \u043d\u0430\u0447\u0430\u0442\u044c \u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c \u0432\u043c\u0435\u0441\u0442\u0435 \u0441 \u043d\u0430\u043c\u0438?</i></b>"
        ),
        "en": (
            f"<b><i>Hi, {{name}}</i></b> {PREMIUM_EMOJI['wave']}\n\n"
            "<i>There is no button in trading that you press once and it starts earning for you.</i>\n\n"
            "<blockquote>\U0001f680 <b>Paradox Bot</b> combines algorithmic analysis and <b>30+ indicators</b> to help you read the market faster and act more systematically.</blockquote>\n\n"
            "<b>The key point:</b>\n\n"
            "\U0001f4b0 <i>it is not a money button</i>\n\n"
            "\u26cf <i>it is a tool you need to work with</i>\n\n"
            "\U0001f4b9 <i>trading is not a quick prize, it requires discipline and practice.</i>\n\n"
            "<b><i>Ready to understand the system and start working with us?</i></b>"
        ),
    },
    "TEAM-01": {
        "ru": "<b>\U0001f525 \u0422\u044b \u0432\u044b\u0431\u0440\u0430\u043b \u0432\u0435\u0442\u043a\u0443 \u043a\u043e\u043c\u0430\u043d\u0434\u044b</b>\n\n\u041d\u0430\u0436\u043c\u0438 \u043a\u043d\u043e\u043f\u043a\u0443 \u043d\u0438\u0436\u0435, \u0447\u0442\u043e\u0431\u044b \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c.",
        "en": "<b>\U0001f525 You selected the team route</b>\n\nTap the button below to continue.",
    },
    "BOT-STEP-01": {
        "ru": "<b>\U0001f511 \u0428\u0430\u0433 1</b>\n\n\u041e\u0442\u043a\u0440\u043e\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043f\u043e \u043d\u0430\u0448\u0435\u0439 \u0441\u0441\u044b\u043b\u043a\u0435, \u0437\u0430\u0442\u0435\u043c \u043e\u0442\u043f\u0440\u0430\u0432\u044c Trader ID \u0447\u0438\u0441\u043b\u043e\u043c \u043e\u0442 6 \u0446\u0438\u0444\u0440.",
        "en": "<b>\U0001f511 Step 1</b>\n\nOpen an account through our link, then send your Trader ID as a number of 6+ digits.",
    },
    "TEAM-STEP-01": {
        "ru": "<b>\U0001f465 \u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043a \u043a\u043e\u043c\u0430\u043d\u0434\u0435</b>\n\n\u041e\u0442\u043a\u0440\u043e\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043f\u043e \u043d\u0430\u0448\u0435\u0439 \u0441\u0441\u044b\u043b\u043a\u0435 \u0438 \u043f\u0440\u0438\u0448\u043b\u0438 Trader ID.",
        "en": "<b>\U0001f465 Team connection</b>\n\nOpen an account through our link and send your Trader ID.",
    },
    "BOT-EXISTING-ACCOUNT": {
        "ru": "\u0415\u0441\u043b\u0438 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0443\u0436\u0435 \u0435\u0441\u0442\u044c, \u043f\u0440\u0438\u0448\u043b\u0438 Trader ID. \u041f\u0440\u0438\u043c\u0435\u0440: <code>ID123456</code>",
        "en": "If you already have an account, send your Trader ID. Example: <code>ID123456</code>",
    },
    "ID-FORMAT": {
        "ru": "\u041f\u0440\u0438\u0448\u043b\u0438 Trader ID \u0432 \u0444\u043e\u0440\u043c\u0430\u0442\u0435 <code>123456</code> \u0438\u043b\u0438 <code>ID123456</code>.",
        "en": "Send Trader ID as <code>123456</code> or <code>ID123456</code>.",
    },
    "ID-NOT-FOUND": {
        "ru": "<b>\u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u043f\u043e \u043d\u0430\u0448\u0435\u0439 \u0441\u0441\u044b\u043b\u043a\u0435</b>\n\n\u041e\u0442\u043a\u0440\u043e\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043f\u043e \u043e\u0434\u043d\u043e\u0439 \u0438\u0437 \u043a\u043d\u043e\u043f\u043e\u043a \u043d\u0438\u0436\u0435 \u0438 \u043f\u0440\u0438\u0448\u043b\u0438 ID \u0435\u0449\u0451 \u0440\u0430\u0437.",
        "en": "<b>Account was not found through our link</b>\n\nOpen an account using one of the buttons below and send your ID again.",
    },
    "TOPUP-01": {
        "ru": "<b>\u2705 \u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u043d\u0430\u0439\u0434\u0435\u043d</b>\n\n\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u0448\u0430\u0433 \u2014 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f.",
        "en": "<b>\u2705 Account found</b>\n\nNext step: deposit verification.",
    },
    "TOPUP-LOW": {
        "ru": "\u041f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435 \u043d\u0438\u0436\u0435 \u043d\u0443\u0436\u043d\u043e\u0433\u043e \u0443\u0441\u043b\u043e\u0432\u0438\u044f.",
        "en": "Deposit is below the required condition.",
    },
    "TOPUP-NOT-FOUND": {
        "ru": "\u041f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435 \u043f\u043e\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e.",
        "en": "Deposit was not found yet.",
    },
    "BOT-SUCCESS": {
        "ru": "<b>\U0001f916 \u0414\u043e\u0441\u0442\u0443\u043f \u043a Paradox Bot \u043e\u0442\u043a\u0440\u044b\u0442</b>",
        "en": "<b>\U0001f916 Paradox Bot access is open</b>",
    },
    "TEAM-SUCCESS": {
        "ru": "<b>\U0001f465 \u0414\u043e\u0441\u0442\u0443\u043f \u043a \u043a\u043e\u043c\u0430\u043d\u0434\u0435 \u043e\u0442\u043a\u0440\u044b\u0442</b>",
        "en": "<b>\U0001f465 Team access is open</b>",
    },
    "REMINDER-03": {
        "ru": "\u041d\u0430\u043f\u043e\u043c\u0438\u043d\u0430\u043d\u0438\u0435: \u0442\u044b \u043c\u043e\u0436\u0435\u0448\u044c \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435.",
        "en": "Reminder: you can continue the connection.",
    },
}
LEGACY_TEXT_FORMAT_TEXTS = {
    "ru": {
        "selected": "\u0422\u0435\u043a\u0441\u0442\u043e\u0432\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442",
        "message": (
            "\u0422\u0435\u043a\u0441\u0442\u043e\u0432\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u043f\u043e\u043a\u0430 \u043d\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d.\n\n"
            "\u0414\u043b\u044f \u0442\u0435\u0441\u0442\u0430 \u043d\u043e\u0432\u043e\u0439 \u0432\u043e\u0440\u043e\u043d\u043a\u0438 \u0438 Mini App \u043e\u0442\u043a\u0440\u043e\u0439 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435."
        ),
        "open_mini_app": "\u26a1 \u041e\u0442\u043a\u0440\u044b\u0442\u044c Mini App",
    },
    "en": {
        "selected": "Text format",
        "message": "Text format is not connected yet.\n\nOpen the Mini App to test the new funnel.",
        "open_mini_app": "\u26a1 Open Mini App",
    },
}
LEGACY_START_TEXTS = {
    "ru": {
        "message": (
            "Привет! 👋\n\n"
            "Профессиональные торговые сигналы для бинарных опционов и форекс рынка.\n\n"
            "Выберите формат работы:"
        ),
        "mini_app": "⚡ Мини-апп (рекомендуется)",
        "text_format": "💬 Текстовый формат",
    },
    "en": {
        "message": (
            "Hi! 👋\n\n"
            "Professional trading signals for binary options and the forex market.\n\n"
            "Choose how you want to work:"
        ),
        "mini_app": "⚡ Mini App (recommended)",
        "text_format": "💬 Text format",
    },
}
TRADER_ID_RE = re.compile(r"^\s*(?:id\s*)?(\d{6,})\s*$", re.IGNORECASE)
SIGNAL_REQUEST_RE = re.compile(
    r"^\s*(?:(?:/signal|signal|СЃРёРіРЅР°Р»)\s+)?([a-z]{3}/?[a-z]{3}(?:\s+otc)?|[a-z]{6}(?:\s+otc)?)\s+(\d{1,2})\s*(?:m|min|РјРёРЅ|Рј)?\s*$",
    re.IGNORECASE,
)

PAIRS_REQUEST_RE = re.compile(
    r"^\s*(?:/pairs|pairs|\u043f\u0430\u0440\u044b)\s+(forex|otc|commodities|stocks|crypto)(?:\s+(commodities|stocks|crypto))?(?:\s+(\d{1,3}))?\s*$",
    re.IGNORECASE,
)
QUOTE_COMMAND_RE = re.compile(r"^\s*(?:/quote|quote|\u043a\u043e\u0442\u0438\u0440\u043e\u0432\u043a\u0430)\s+(.+?)\s*$", re.IGNORECASE)
QUOTE_CATEGORIES = {"forex", "otc", "commodities", "stocks", "crypto"}
PAIR_CATEGORIES = {"commodities", "stocks", "crypto"}

BOT_TEXTS = {
    "ru": {
        "start": (
            "РџСЂРёРІРµС‚! рџ‘‹\n\n"
            "РџСЂРѕС„РµСЃСЃРёРѕРЅР°Р»СЊРЅС‹Рµ С‚РѕСЂРіРѕРІС‹Рµ СЃРёРіРЅР°Р»С‹ РґР»СЏ Р±РёРЅР°СЂРЅС‹С… РѕРїС†РёРѕРЅРѕРІ Рё С„РѕСЂРµРєСЃ СЂС‹РЅРєР°.\n\n"
            "Р’С‹Р±РµСЂРёС‚Рµ С„РѕСЂРјР°С‚ СЂР°Р±РѕС‚С‹:"
        ),
        "mini_app": "вљЎ РњРёРЅРё-Р°РїРї (СЂРµРєРѕРјРµРЅРґСѓРµС‚СЃСЏ)",
        "text_format": "рџ’¬ РўРµРєСЃС‚РѕРІС‹Р№ С„РѕСЂРјР°С‚",
        "text_selected": "РўРµРєСЃС‚РѕРІС‹Р№ С„РѕСЂРјР°С‚ РІС‹Р±СЂР°РЅ",
        "text_selected_message": (
            "РўРµРєСЃС‚РѕРІС‹Р№ С„РѕСЂРјР°С‚ РІС‹Р±СЂР°РЅ.\n\n"
            "РЎРёРіРЅР°Р»С‹ Р±СѓРґСѓС‚ РїСЂРёС…РѕРґРёС‚СЊ СЃРѕРѕР±С‰РµРЅРёСЏРјРё Telegram. РќР° РїРµСЂРІРѕРј СЌС‚Р°РїРµ СЂРµР°Р»СЊРЅС‹Рµ СЃРёРіРЅР°Р»С‹ РµС‰Рµ РЅРµ РїРѕРґРєР»СЋС‡РµРЅС‹."
        ),
        "open_mini_app": "вљЎ РћС‚РєСЂС‹С‚СЊ Mini App",
        "team_start": "Р’С‹ РІС‹Р±СЂР°Р»Рё РјР°СЂС€СЂСѓС‚ РєРѕРјР°РЅРґС‹.\n\nРќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ РЅРёР¶Рµ, С‡С‚РѕР±С‹ РІРѕР№С‚Рё РІ РєРѕРјР°РЅРґСѓ Paradox FX.",
        "join_team": "Р’РћР™РўР Р’ РљРћРњРђРќР”РЈ",
    },
    "en": {
        "start": (
            "Hi! рџ‘‹\n\n"
            "Professional trading signals for binary options and the forex market.\n\n"
            "Choose how you want to work:"
        ),
        "mini_app": "вљЎ Mini App (recommended)",
        "text_format": "рџ’¬ Text format",
        "text_selected": "Text format selected",
        "text_selected_message": (
            "Text format selected.\n\n"
            "Signals will be delivered as Telegram messages. Real signals are not connected at this stage."
        ),
        "open_mini_app": "вљЎ Open Mini App",
        "team_start": "You selected the team route.\n\nTap the button below to join the Paradox FX team.",
        "join_team": "JOIN THE TEAM",
    },
    "es": {
        "start": "ВЎHola! рџ‘‹\n\nSeГ±ales profesionales para opciones binarias y forex.\n\nElige el formato de trabajo:",
        "mini_app": "вљЎ Mini App (recomendado)",
        "text_format": "рџ’¬ Formato de texto",
        "text_selected": "Formato de texto seleccionado",
        "text_selected_message": "Formato de texto seleccionado.\n\nLas seГ±ales llegarГЎn como mensajes de Telegram. Las seГ±ales reales aГєn no estГЎn conectadas.",
        "open_mini_app": "вљЎ Abrir Mini App",
        "team_start": "Has elegido la ruta del equipo.\n\nPulsa el botГіn de abajo para unirte al equipo Paradox FX.",
        "join_team": "UNIRSE AL EQUIPO",
    },
    "pt": {
        "start": "OlГЎ! рџ‘‹\n\nSinais profissionais para opГ§Гµes binГЎrias e forex.\n\nEscolha o formato de trabalho:",
        "mini_app": "вљЎ Mini App (recomendado)",
        "text_format": "рџ’¬ Formato de texto",
        "text_selected": "Formato de texto selecionado",
        "text_selected_message": "Formato de texto selecionado.\n\nOs sinais chegarГЈo como mensagens do Telegram. Sinais reais ainda nГЈo estГЈo conectados.",
        "open_mini_app": "вљЎ Abrir Mini App",
        "team_start": "VocГЄ escolheu a rota da equipe.\n\nToque no botГЈo abaixo para entrar na equipe Paradox FX.",
        "join_team": "ENTRAR NA EQUIPE",
    },
    "tr": {
        "start": "Merhaba! рџ‘‹\n\nBinary opsiyonlar ve forex piyasasД± iГ§in profesyonel iЕџlem sinyalleri.\n\nГ‡alД±Еџma formatД±nД± seГ§in:",
        "mini_app": "вљЎ Mini App (Г¶nerilir)",
        "text_format": "рџ’¬ Metin formatД±",
        "text_selected": "Metin formatД± seГ§ildi",
        "text_selected_message": "Metin formatД± seГ§ildi.\n\nSinyaller Telegram mesajlarД± olarak gelecek. GerГ§ek sinyaller bu aЕџamada baДџlД± deДџil.",
        "open_mini_app": "вљЎ Mini App'i aГ§",
        "team_start": "TakД±m rotasД±nД± seГ§tiniz.\n\nParadox FX ekibine katД±lmak iГ§in aЕџaДџД±daki dГјДџmeye dokunun.",
        "join_team": "TAKIMA KATIL",
    },
    "ar": {
        "start": "Щ…Ш±Ш­ШЁШ§! рџ‘‹\n\nШҐШґШ§Ш±Ш§ШЄ ШЄШЇШ§Щ€Щ„ Ш§Ш­ШЄШ±Ш§ЩЃЩЉШ© Щ„Щ„Ш®ЩЉШ§Ш±Ш§ШЄ Ш§Щ„Ш«Щ†Ш§Ш¦ЩЉШ© Щ€ШіЩ€Щ‚ Ш§Щ„ЩЃЩ€Ш±ЩѓШі.\n\nШ§Ш®ШЄШ± Ш·Ш±ЩЉЩ‚Ш© Ш§Щ„Ш№Щ…Щ„:",
        "mini_app": "вљЎ Mini App (Щ…Щ€ШµЩ‰ ШЁЩ‡)",
        "text_format": "рџ’¬ ШЄЩ†ШіЩЉЩ‚ Щ†ШµЩЉ",
        "text_selected": "ШЄЩ… Ш§Ш®ШЄЩЉШ§Ш± Ш§Щ„ШЄЩ†ШіЩЉЩ‚ Ш§Щ„Щ†ШµЩЉ",
        "text_selected_message": "ШЄЩ… Ш§Ш®ШЄЩЉШ§Ш± Ш§Щ„ШЄЩ†ШіЩЉЩ‚ Ш§Щ„Щ†ШµЩЉ.\n\nШіШЄШµЩ„ Ш§Щ„ШҐШґШ§Ш±Ш§ШЄ ЩѓШ±ШіШ§Ш¦Щ„ Telegram. Ш§Щ„ШҐШґШ§Ш±Ш§ШЄ Ш§Щ„Ш­Щ‚ЩЉЩ‚ЩЉШ© ШєЩЉШ± Щ…ШЄШµЩ„Ш© ЩЃЩЉ Щ‡Ш°Щ‡ Ш§Щ„Щ…Ш±Ш­Щ„Ш©.",
        "open_mini_app": "вљЎ ЩЃШЄШ­ Mini App",
        "team_start": "Щ„Щ‚ШЇ Ш§Ш®ШЄШ±ШЄ Щ…ШіШ§Ш± Ш§Щ„ЩЃШ±ЩЉЩ‚.\n\nШ§Ш¶ШєШ· Ш№Щ„Щ‰ Ш§Щ„ШІШ± ШЈШЇЩ†Ш§Щ‡ Щ„Щ„Ш§Щ†Ш¶Щ…Ш§Щ… ШҐЩ„Щ‰ ЩЃШ±ЩЉЩ‚ Paradox FX.",
        "join_team": "Ш§Щ†Ш¶Щ… ШҐЩ„Щ‰ Ш§Щ„ЩЃШ±ЩЉЩ‚",
    },
}

TRADER_ID_TEXTS = {
    "ru": {
        "not_found": "\u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u043f\u043e \u043d\u0430\u0448\u0435\u0439 \u0441\u0441\u044b\u043b\u043a\u0435",
        "unavailable": "\u041f\u0430\u0440\u0442\u043d\u0451\u0440\u0441\u043a\u0430\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435.",
        "found": "\u2705 \u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u043d\u0430\u0439\u0434\u0435\u043d \u043f\u043e \u043d\u0430\u0448\u0435\u0439 \u0441\u0441\u044b\u043b\u043a\u0435.",
    },
    "en": {
        "not_found": "Account was not found through our link",
        "unavailable": "Partner verification is temporarily unavailable. Try again later.",
        "found": "\u2705 Account was found through our link.",
    },
}
SIGNAL_TEXTS = {
    "ru": {
        "unavailable": "\u0421\u0435\u0440\u0432\u0438\u0441 \u0430\u043d\u0430\u043b\u0438\u0437\u0430 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435.",
        "bad_expiry": "\u042d\u043a\u0441\u043f\u0438\u0440\u0430\u0446\u0438\u044f \u0434\u043e\u043b\u0436\u043d\u0430 \u0431\u044b\u0442\u044c \u043e\u0442 1 \u0434\u043e 60 \u043c\u0438\u043d\u0443\u0442.",
        "title": "\U0001f4e1 <b>Paradox API \u0441\u0438\u0433\u043d\u0430\u043b</b>",
        "asset": "\u0410\u043a\u0442\u0438\u0432",
        "expiry": "\u042d\u043a\u0441\u043f\u0438\u0440\u0430\u0446\u0438\u044f",
        "direction": "\u041d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435",
        "confidence": "\u0423\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c",
        "price": "\u0426\u0435\u043d\u0430",
        "source": "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a",
        "reason": "\u041f\u0440\u0438\u0447\u0438\u043d\u0430",
        "unknown": "\u043d/\u0434",
        "minutes": "\u043c\u0438\u043d",
    },
    "en": {
        "unavailable": "Analysis service is temporarily unavailable. Try again later.",
        "bad_expiry": "Expiration must be from 1 to 60 minutes.",
        "title": "\U0001f4e1 <b>Paradox API signal</b>",
        "asset": "Asset",
        "expiry": "Expiration",
        "direction": "Direction",
        "confidence": "Confidence",
        "price": "Price",
        "source": "Source",
        "reason": "Reason",
        "unknown": "n/a",
        "minutes": "min",
    },
}

API_TEST_TEXTS = {
    "ru": {
        "unavailable": "\u0422\u0435\u0441\u0442 Devsbite \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0442\u043e\u043a\u0435\u043d \u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0435 \u0440\u0430\u0437.",
        "pairs_title": "\U0001f9ea <b>Devsbite pairs</b>",
        "quote_title": "\U0001f4c8 <b>Devsbite quote</b>",
        "market": "\u0420\u044b\u043d\u043e\u043a",
        "category": "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f",
        "symbol": "\u0410\u043a\u0442\u0438\u0432",
        "min_payout": "\u041c\u0438\u043d. payout",
        "available": "\u041d\u0430\u0439\u0434\u0435\u043d\u043e",
        "shown": "\u041f\u043e\u043a\u0430\u0437\u0430\u043d\u043e",
        "payout": "payout",
        "status": "\u0421\u0442\u0430\u0442\u0443\u0441",
        "price": "\u0426\u0435\u043d\u0430",
        "source": "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a",
        "fetched_at": "\u0412\u0440\u0435\u043c\u044f API",
        "message": "\u0421\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435",
        "empty": "\u0412 \u043e\u0442\u0432\u0435\u0442\u0435 \u043d\u0435\u0442 \u0441\u043f\u0438\u0441\u043a\u0430 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u043e\u0432.",
        "unknown": "\u043d/\u0434",
    },
    "en": {
        "unavailable": "Devsbite test is temporarily unavailable. Check the token and try again.",
        "pairs_title": "\U0001f9ea <b>Devsbite pairs</b>",
        "quote_title": "\U0001f4c8 <b>Devsbite quote</b>",
        "market": "Market",
        "category": "Category",
        "symbol": "Asset",
        "min_payout": "Min payout",
        "available": "Available",
        "shown": "Shown",
        "payout": "payout",
        "status": "Status",
        "price": "Price",
        "source": "Source",
        "fetched_at": "API time",
        "message": "Message",
        "empty": "The response does not contain an instruments list.",
        "unknown": "n/a",
    },
}


def ensure_telegram_configured() -> None:
    if not settings.telegram_bot_token or not settings.telegram_webapp_url:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")


def telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def normalize_language(language_code: str | None) -> str:
    if not language_code:
        return "en"

    language = language_code.lower().split("-")[0]
    return language if language in SUPPORTED_LANGUAGES else "en"


def normalize_funnel_language(language_code: str | None) -> str:
    language = normalize_language(language_code)
    return language if language in FUNNEL_LANGUAGES else "en"


def user_display_name(user: dict[str, Any] | None, language: str) -> str:
    fallback = "\u0434\u0440\u0443\u0433" if normalize_funnel_language(language) == "ru" else "friend"
    if not user:
        return fallback

    raw_name = user.get("first_name") or user.get("username")
    if not raw_name:
        return fallback

    return escape(str(raw_name))


def parse_start_context(text: str | None) -> tuple[str, str | None] | None:
    if not text:
        return None

    parts = text.strip().split(maxsplit=1)
    if not parts or not parts[0].startswith("/start"):
        return None

    if len(parts) < 2:
        return "BOT", None

    payload = parts[1].strip().lower()
    return START_DEEP_LINKS.get(payload)


def save_start_context(db: Session, user: dict[str, Any], language: str, funnel_route: str) -> None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is None:
        settings_row = UserSettings(
            telegram_id=telegram_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
            language=language,
            funnel_route=funnel_route,
        )
        db.add(settings_row)
    else:
        settings_row.username = user.get("username")
        settings_row.first_name = user.get("first_name")
        settings_row.language = language
        settings_row.funnel_route = funnel_route

    db.commit()


def funnel_texts(language: str) -> dict[str, str]:
    return FUNNEL_BUTTON_TEXTS.get(normalize_funnel_language(language), FUNNEL_BUTTON_TEXTS["en"])


def is_funnel_test_user(user: dict[str, Any]) -> bool:
    return settings.telegram_funnel_test_mode_enabled and is_funnel_user_allowed(user)


def has_funnel_access(db: Session, user: dict[str, Any]) -> bool:
    telegram_id = user.get("id")
    if telegram_id is None:
        return False

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    return bool(settings_row and settings_row.funnel_access_granted)


def grant_funnel_access(db: Session, user: dict[str, Any]) -> None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is None:
        settings_row = UserSettings(
            telegram_id=telegram_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
            funnel_access_granted=True,
        )
        db.add(settings_row)
    else:
        settings_row.username = user.get("username")
        settings_row.first_name = user.get("first_name")
        settings_row.funnel_access_granted = True

    db.commit()


def should_show_mini_app_menu(db: Session, user: dict[str, Any]) -> bool:
    return not is_funnel_test_user(user) or has_funnel_access(db, user)


def is_test_access_code(text: str) -> bool:
    access_code = settings.telegram_funnel_test_access_code.strip()
    return bool(access_code) and text.strip().casefold() == access_code.casefold()


def set_chat_mini_app_menu(client: httpx.Client, chat_id: int, language: str, *, enabled: bool) -> None:
    menu_button: dict[str, Any]
    if enabled:
        menu_button = {
            "type": "web_app",
            "text": funnel_texts(language)["open_bot"],
            "web_app": {"url": settings.telegram_webapp_url},
        }
    else:
        menu_button = {"type": "commands"}

    try:
        client.post(
            telegram_api_url("setChatMenuButton"),
            json={
                "chat_id": chat_id,
                "menu_button": menu_button,
            },
        ).raise_for_status()
    except Exception as error:
        print(f"telegram_menu_button_update_failed chat_id={chat_id} enabled={enabled} detail={telegram_error_detail(error)}")


def funnel_ref_keyboard(language: str, *, include_existing_account: bool = True) -> dict[str, Any] | None:
    texts = funnel_texts(language)
    keyboard = []
    if settings.pocket_option_ref_ru_url:
        keyboard.append([{"text": texts["ref_ru"], "url": settings.pocket_option_ref_ru_url}])
    if settings.pocket_option_ref_ww_url:
        keyboard.append([{"text": texts["ref_world"], "url": settings.pocket_option_ref_ww_url}])
    if include_existing_account:
        keyboard.append([{"text": texts["existing_account"], "callback_data": "funnel:existing_account"}])
    return {"inline_keyboard": keyboard} if keyboard else None


def funnel_node_keyboard(node_code: str, language: str) -> dict[str, Any] | None:
    texts = funnel_texts(language)

    if node_code == "BOT-01":
        return {"inline_keyboard": [[{"text": texts["want_bot"], "callback_data": "funnel:bot_start"}]]}

    if node_code == "TEAM-01":
        return {"inline_keyboard": [[{"text": texts["want_team"], "callback_data": "funnel:team_start"}]]}

    if node_code in {"BOT-STEP-01", "TEAM-STEP-01"}:
        return funnel_ref_keyboard(language, include_existing_account=True)

    if node_code in {"BOT-EXISTING-ACCOUNT", "ID-NOT-FOUND"}:
        return funnel_ref_keyboard(language, include_existing_account=False)

    if node_code in {"TOPUP-01", "TOPUP-LOW", "TOPUP-NOT-FOUND"}:
        return {"inline_keyboard": [[{"text": texts["check_topup"], "callback_data": "funnel:check_topup"}]]}

    if node_code == "BOT-SUCCESS":
        return {"inline_keyboard": [[{"text": texts["open_bot"], "web_app": {"url": settings.telegram_webapp_url}}]]}

    if node_code == "TEAM-SUCCESS":
        keyboard = [[{"text": texts["open_bot"], "web_app": {"url": settings.telegram_webapp_url}}]]
        if settings.team_vip_url:
            keyboard.append([{"text": texts["join_team"], "url": settings.team_vip_url}])
        return {"inline_keyboard": keyboard}

    if node_code == "REMINDER-03":
        return {"inline_keyboard": [[{"text": texts["want_team"], "callback_data": "funnel:team_start"}]]}

    return None


def copy_funnel_node(
    client: httpx.Client,
    chat_id: int,
    node_code: str,
    language: str,
    user: dict[str, Any] | None = None,
) -> None:
    text_by_language = FUNNEL_NODE_TEXTS.get(node_code)
    if text_by_language is None:
        raise HTTPException(status_code=500, detail=f"Funnel node text is not configured: {node_code}")

    text = text_by_language.get(normalize_funnel_language(language), text_by_language["en"])
    text = text.replace("{\u0438\u043c\u044f}", "{name}").replace("{name}", user_display_name(user, language))
    photo_path = FUNNEL_NODE_PHOTOS.get(node_code)
    if photo_path is not None and photo_path.exists():
        with photo_path.open("rb") as photo:
            client.post(
                telegram_api_url("sendPhoto"),
                data={"chat_id": chat_id},
                files={"photo": (photo_path.name, photo, "image/png")},
            ).raise_for_status()

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    reply_markup = funnel_node_keyboard(node_code, language)
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    response = client.post(telegram_api_url("sendMessage"), json=payload)
    response.raise_for_status()
    print(f"telegram_send_node node={node_code} chat_id={chat_id}")


def get_saved_language(db: Session, user: dict[str, Any]) -> str | None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return None

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is None or settings_row.language not in SUPPORTED_LANGUAGES:
        return None

    return settings_row.language


def get_saved_context(db: Session, user: dict[str, Any]) -> tuple[str | None, str | None]:
    telegram_id = user.get("id")
    if telegram_id is None:
        return None, None

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is None:
        return None, None

    language = settings_row.language if settings_row.language in SUPPORTED_LANGUAGES else None
    funnel_route = settings_row.funnel_route if settings_row.funnel_route in {"BOT", "TEAM"} else None
    return funnel_route, language


def send_html_message(client: httpx.Client, chat_id: int, text: str) -> None:
    client.post(
        telegram_api_url("sendMessage"),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        },
    ).raise_for_status()


def send_legacy_start_message(client: httpx.Client, chat_id: int, language: str) -> None:
    texts = LEGACY_START_TEXTS.get(normalize_funnel_language(language), LEGACY_START_TEXTS["en"])
    client.post(
        telegram_api_url("sendMessage"),
        json={
            "chat_id": chat_id,
            "text": texts["message"],
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": texts["mini_app"], "web_app": {"url": settings.telegram_webapp_url}}],
                    [{"text": texts["text_format"], "callback_data": "text_format"}],
                ]
            },
        },
    ).raise_for_status()


def telegram_error_detail(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.text
    if isinstance(error, HTTPException):
        return str(error.detail)
    return repr(error)


def send_funnel_delivery_error(client: httpx.Client, chat_id: int, node_code: str, error: Exception) -> None:
    detail = telegram_error_detail(error)
    print(f"telegram_send_node_failed node={node_code} detail={detail}")
    send_html_message(
        client,
        chat_id,
        (
            "\u26a0\ufe0f <b>\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0443\u0437\u0435\u043b "
            f"{escape(node_code)}</b>\n\n"
            "\u041f\u0440\u043e\u0432\u0435\u0440\u044c:\n"
            "\u2022 TELEGRAM_BOT_TOKEN\n"
            "\u2022 TELEGRAM_WEBAPP_URL\n"
            "\u2022 \u0432\u0430\u043b\u0438\u0434\u043d\u043e\u0441\u0442\u044c inline-\u043a\u043d\u043e\u043f\u043e\u043a \u0438 URL \u0432 env\n\n"
            f"<code>{escape(detail[:700])}</code>"
        ),
    )


def log_telegram_media_ids(message: dict[str, Any]) -> None:
    sticker = message.get("sticker")
    if isinstance(sticker, dict):
        print(
            "telegram_sticker "
            f"emoji={sticker.get('emoji')} "
            f"file_id={sticker.get('file_id')} "
            f"custom_emoji_id={sticker.get('custom_emoji_id')}"
        )

    entities = []
    for key in ("entities", "caption_entities"):
        value = message.get(key)
        if isinstance(value, list):
            entities.extend(value)

    custom_emoji_ids = [
        entity.get("custom_emoji_id")
        for entity in entities
        if isinstance(entity, dict) and entity.get("type") == "custom_emoji" and entity.get("custom_emoji_id")
    ]
    if custom_emoji_ids:
        print(f"telegram_custom_emoji_ids={custom_emoji_ids}")


def utf16_slice(text: str, offset: int, length: int) -> str:
    raw = text.encode("utf-16-le")
    start = offset * 2
    end = (offset + length) * 2
    try:
        return raw[start:end].decode("utf-16-le")
    except UnicodeDecodeError:
        return text[offset : offset + length]


def custom_emoji_report(message: dict[str, Any]) -> str | None:
    rows: list[tuple[str, str]] = []

    for text_key, entities_key in (("text", "entities"), ("caption", "caption_entities")):
        text = message.get(text_key)
        entities = message.get(entities_key)
        if not isinstance(text, str) or not isinstance(entities, list):
            continue

        for entity in entities:
            if not isinstance(entity, dict) or entity.get("type") != "custom_emoji":
                continue
            custom_emoji_id = entity.get("custom_emoji_id")
            offset = entity.get("offset")
            length = entity.get("length")
            if not custom_emoji_id or not isinstance(offset, int) or not isinstance(length, int):
                continue

            emoji = utf16_slice(text, offset, length) or "?"
            rows.append((emoji, str(custom_emoji_id)))

    sticker = message.get("sticker")
    if isinstance(sticker, dict) and sticker.get("custom_emoji_id"):
        rows.append((str(sticker.get("emoji") or "?"), str(sticker["custom_emoji_id"])))

    if not rows:
        return None

    unique_rows = list(dict.fromkeys(rows))
    all_ids = "\n".join(custom_emoji_id for _, custom_emoji_id in unique_rows)
    lines = [
        f"\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b premium emoji: <b>{len(unique_rows)}</b>",
        "",
        "<b>\u0412\u0441\u0435 custom_emoji_id:</b>",
        f"<code>{escape(all_ids)}</code>",
    ]

    for index, (emoji, custom_emoji_id) in enumerate(unique_rows, start=1):
        html = f'<tg-emoji emoji-id="{custom_emoji_id}">{emoji}</tg-emoji>'
        markdown = f"![{emoji}](tg://emoji?id={custom_emoji_id})"
        lines.extend(
            [
                "",
                f"<b>{index}. {escape(emoji)}</b>",
                f"custom_emoji_id: <code>{escape(custom_emoji_id)}</code>",
                "HTML:",
                f"<code>{escape(html)}</code>",
                "Markdown:",
                f"<code>{escape(markdown)}</code>",
            ]
        )

    return "\n".join(lines)


def handle_custom_emoji_id_message(client: httpx.Client, chat_id: int, message: dict[str, Any]) -> bool:
    command_text = message.get("text") or message.get("caption") or ""
    if not isinstance(command_text, str) or not command_text.strip().lower().startswith(("/emoji_ids", "/emoji")):
        return False

    report = custom_emoji_report(message)
    if report is None:
        return False

    client.post(
        telegram_api_url("sendMessage"),
        json={
            "chat_id": chat_id,
            "text": report,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    ).raise_for_status()
    return True


def is_funnel_user_allowed(user: dict[str, Any]) -> bool:
    allowed_ids = settings.telegram_funnel_allowed_user_id_set
    telegram_id = user.get("id")
    return isinstance(telegram_id, int) and telegram_id in allowed_ids


def parse_pairs_request(text: str) -> tuple[str, str | None, int] | None:
    match = PAIRS_REQUEST_RE.match(text)
    if match is None:
        return None

    market = match.group(1).lower()
    category = match.group(2).lower() if match.group(2) else None
    min_payout = int(match.group(3) or 80)
    if market in PAIR_CATEGORIES:
        category = market
        market = "otc"
    return market, category, min(max(min_payout, 0), 100)


def normalize_quote_symbol(symbol: str) -> str:
    normalized = re.sub(r"\s+", " ", symbol.strip())
    if re.match(r"^[a-z]{3}/?[a-z]{3}(?:\s+otc)?$", normalized, re.IGNORECASE):
        return normalized.upper()
    return normalized


def infer_quote_category(symbol: str) -> str:
    return "otc" if " OTC" in symbol.upper() else "forex"


def parse_quote_request(text: str) -> tuple[str, str, int | None] | None:
    match = QUOTE_COMMAND_RE.match(text)
    if match is None:
        return None

    tokens = match.group(1).split()
    if not tokens:
        return None

    history_seconds: int | None = None
    if tokens[-1].isdigit():
        history_seconds = max(1, min(int(tokens.pop()), 3600))

    category = tokens[0].lower()
    if category in QUOTE_CATEGORIES:
        tokens.pop(0)
    else:
        category = infer_quote_category(" ".join(tokens))

    symbol = normalize_quote_symbol(" ".join(tokens))
    if not symbol:
        return None

    return category, symbol, history_seconds


def extract_payload_items(payload: dict[str, Any]) -> list[Any]:
    for key in ("pairs", "assets", "items", "data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested_items = extract_payload_items(value)
            if nested_items:
                return nested_items
    return []


def extract_payload_object(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("quote", "data", "result", "item"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def scalar_text(value: Any, fallback: str) -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def first_existing(payload: dict[str, Any], keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return str(payload[key])
    return fallback


def format_pair_item(item: Any, index: int, texts: dict[str, str]) -> str:
    if isinstance(item, dict):
        symbol = first_existing(item, ("symbol", "name", "pair", "resolved_symbol"), texts["unknown"])
        payout = first_existing(item, ("payout", "profit", "percent", "return"), "")
        status = first_existing(item, ("market_status", "status", "state"), "")

        details = []
        if payout:
            details.append(f'{texts["payout"]}: {escape(payout)}')
        if status:
            details.append(escape(status))

        suffix = f" В· {' В· '.join(details)}" if details else ""
        return f"{index}. <b>{escape(symbol)}</b>{suffix}"

    return f"{index}. <b>{escape(str(item))}</b>"


def format_pair_item_clean(item: Any, index: int, texts: dict[str, str]) -> str:
    if isinstance(item, dict):
        symbol = first_existing(item, ("symbol", "name", "pair", "resolved_symbol"), texts["unknown"])
        payout = first_existing(item, ("payout", "profit", "percent", "return"), "")
        status = first_existing(item, ("market_status", "status", "state"), "")

        details = []
        if payout:
            details.append(f'{texts["payout"]}: {escape(payout)}')
        if status:
            details.append(escape(status))

        suffix = f" - {' - '.join(details)}" if details else ""
        return f"{index}. <b>{escape(symbol)}</b>{suffix}"

    return f"{index}. <b>{escape(str(item))}</b>"


def format_pairs_response(
    language: str,
    market: str,
    category: str | None,
    min_payout: int,
    payload: dict[str, Any],
) -> str:
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    items = extract_payload_items(payload)
    count = payload.get("count")
    total = count if isinstance(count, int) else len(items)
    shown_items = items[:15]

    lines = [
        texts["pairs_title"],
        "",
        f'{texts["market"]}: <b>{escape(market.upper())}</b>',
    ]
    if category:
        lines.append(f'{texts["category"]}: <b>{escape(category)}</b>')
    lines.extend(
        [
            f'{texts["min_payout"]}: <b>{min_payout}%</b>',
            f'{texts["available"]}: <b>{escape(str(total))}</b>',
            f'{texts["shown"]}: <b>{len(shown_items)}</b>',
            "",
        ]
    )

    if not shown_items:
        lines.append(texts["empty"])
        return "\n".join(lines)

    lines.append("<blockquote>")
    lines.extend(format_pair_item_clean(item, index, texts) for index, item in enumerate(shown_items, start=1))
    lines.append("</blockquote>")
    return "\n".join(lines)


def format_quote_response(language: str, category: str, symbol: str, payload: dict[str, Any]) -> str:
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    quote = extract_payload_object(payload)
    price = first_existing(quote, ("price", "bid", "ask", "last", "value", "close"), texts["unknown"])
    status = first_existing(quote, ("market_status", "status", "state"), texts["unknown"])
    source = first_existing(quote, ("source", "provider"), texts["unknown"])
    fetched_at = first_existing(quote, ("fetched_at", "time", "timestamp", "updated_at"), texts["unknown"])
    message = scalar_text(quote.get("message") or payload.get("message"), "")

    lines = [
        texts["quote_title"],
        "",
        f'{texts["category"]}: <b>{escape(category)}</b>',
        f'{texts["symbol"]}: <b>{escape(symbol)}</b>',
        f'{texts["price"]}: <code>{escape(price)}</code>',
        f'{texts["status"]}: <b>{escape(status)}</b>',
        f'{texts["source"]}: <code>{escape(source)}</code>',
        f'{texts["fetched_at"]}: <code>{escape(fetched_at)}</code>',
    ]

    if message:
        lines.extend(["", f'{texts["message"]}: {escape(message)}'])

    return "\n".join(lines)


def parse_signal_request(text: str) -> tuple[str, int] | None:
    match = SIGNAL_REQUEST_RE.match(text)
    if match is None:
        return None

    symbol = match.group(1).strip().upper()
    expiry_min = int(match.group(2))
    if expiry_min < 1 or expiry_min > 60:
        raise ValueError("invalid expiry")

    if " OTC" not in symbol:
        symbol = symbol.replace("/", "")

    symbol = re.sub(r"\s+", " ", symbol)
    return symbol, expiry_min


def format_signal_response(language: str, symbol: str, expiry_min: int, payload: dict[str, Any]) -> str:
    texts = SIGNAL_TEXTS.get(language, SIGNAL_TEXTS["en"])
    direction = payload.get("signal") or payload.get("direction") or texts["unknown"]
    confidence = payload.get("confidence", texts["unknown"])
    price = payload.get("price", texts["unknown"])
    source = payload.get("decision_source") or payload.get("mode") or texts["unknown"]
    reason = payload.get("decision_reason") or payload.get("reason") or payload.get("message")

    lines = [
        texts["title"],
        "",
        f'{texts["asset"]}: <b>{escape(str(symbol))}</b>',
        f'{texts["expiry"]}: <b>{expiry_min} {texts["minutes"]}</b>',
        f'{texts["direction"]}: <b>{escape(str(direction))}</b>',
        f'{texts["confidence"]}: <b>{escape(str(confidence))}%</b>',
        f'{texts["price"]}: <code>{escape(str(price))}</code>',
        f'{texts["source"]}: <code>{escape(str(source))}</code>',
    ]

    if reason:
        lines.extend(["", f'{texts["reason"]}: {escape(str(reason))}'])

    return "\n".join(lines)


def handle_signal_request_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    try:
        signal_request = parse_signal_request(text)
    except ValueError:
        funnel_route, language = get_saved_context(db, user)
        language = language or normalize_language(user.get("language_code"))
        if funnel_route == "BOT":
            with httpx.Client(timeout=10) as client:
                send_html_message(client, chat_id, SIGNAL_TEXTS.get(language, SIGNAL_TEXTS["en"])["bad_expiry"])
            return True
        return False

    if signal_request is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route != "BOT":
        return False

    language = language or normalize_language(user.get("language_code"))
    texts = SIGNAL_TEXTS.get(language, SIGNAL_TEXTS["en"])
    symbol, expiry_min = signal_request

    with httpx.Client(timeout=10) as client:
        try:
            payload = get_combined_analysis(symbol=symbol, expiry_min=expiry_min)
        except (DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        send_html_message(client, chat_id, format_signal_response(language, symbol, expiry_min, payload))
        return True


def handle_test_access_code_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    if not is_funnel_test_user(user) or not is_test_access_code(text):
        return False

    funnel_route, language = get_saved_context(db, user)
    language = normalize_funnel_language(language or user.get("language_code"))
    funnel_route = funnel_route or "BOT"
    save_start_context(db, user, language, funnel_route)
    grant_funnel_access(db, user)

    node_code = "TEAM-SUCCESS" if funnel_route == "TEAM" else "BOT-SUCCESS"
    with httpx.Client(timeout=10) as client:
        set_chat_mini_app_menu(client, chat_id, language, enabled=True)
        copy_funnel_node(client=client, chat_id=chat_id, node_code=node_code, language=language, user=user)
    return True


def handle_pairs_request_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    pairs_request = parse_pairs_request(text)
    if pairs_request is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route != "BOT":
        return False

    language = language or normalize_language(user.get("language_code"))
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    market, category, min_payout = pairs_request

    with httpx.Client(timeout=10) as client:
        try:
            payload = get_pairs(market=market, min_payout=min_payout, category=category)
        except (DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        send_html_message(client, chat_id, format_pairs_response(language, market, category, min_payout, payload))
        return True


def handle_quote_request_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    quote_request = parse_quote_request(text)
    if quote_request is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route != "BOT":
        return False

    language = language or normalize_language(user.get("language_code"))
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    category, symbol, history_seconds = quote_request

    with httpx.Client(timeout=10) as client:
        try:
            payload = get_quote(category=category, symbol=symbol, history_seconds=history_seconds)
        except (DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        send_html_message(client, chat_id, format_quote_response(language, category, symbol, payload))
        return True


def handle_trader_id_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    match = TRADER_ID_RE.match(text)
    if match is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route not in {"BOT", "TEAM"}:
        return False

    language = normalize_funnel_language(language or user.get("language_code"))
    texts = TRADER_ID_TEXTS.get(language, TRADER_ID_TEXTS["en"])
    trader_id = match.group(1)

    with httpx.Client(timeout=10) as client:
        try:
            get_user_info(trader_id)
        except PocketOptionApiError as error:
            if error.status_code == 404:
                copy_funnel_node(client, chat_id, "ID-NOT-FOUND", language, user=user)
                return True

            send_html_message(client, chat_id, texts["unavailable"])
            return True
        except (PocketOptionConfigError, PocketOptionRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        copy_funnel_node(client, chat_id, "TOPUP-01", language, user=user)
        return True


def handle_invalid_trader_id_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    if text.startswith("/"):
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route not in {"BOT", "TEAM"}:
        return False

    language = normalize_funnel_language(language or user.get("language_code"))
    with httpx.Client(timeout=10) as client:
        copy_funnel_node(client, chat_id, "ID-FORMAT", language, user=user)
    return True


@router.post("/webhook", summary="Telegram bot webhook")
def telegram_webhook(update: dict[str, Any], db: Session = Depends(get_db)):
    ensure_telegram_configured()

    callback_query = update.get("callback_query")
    if callback_query:
        callback_data = callback_query.get("data")
        if callback_data == "text_format":
            handle_callback_query(callback_query, db)
            return {"ok": True}
        if not settings.telegram_funnel_enabled:
            print("telegram_funnel disabled")
            return {"ok": True}
        if callback_data and callback_data.startswith("funnel:") and not is_funnel_user_allowed(callback_query.get("from") or {}):
            print(f"telegram_funnel callback_user_not_allowed telegram_id={(callback_query.get('from') or {}).get('id')}")
            return {"ok": True}
        handle_callback_query(callback_query, db)
        return {"ok": True}

    message = update.get("message") or {}
    log_telegram_media_ids(message)
    text = message.get("text")
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")

    if chat_id is None:
        return {"ok": True}

    if not settings.telegram_funnel_enabled:
        if text and text.startswith("/start"):
            language = normalize_funnel_language(user.get("language_code"))
            with httpx.Client(timeout=10) as client:
                set_chat_mini_app_menu(client, chat_id, language, enabled=True)
                send_legacy_start_message(client, chat_id, language)
        else:
            print("telegram_funnel disabled")
        return {"ok": True}

    if not is_funnel_user_allowed(user):
        with httpx.Client(timeout=10) as client:
            language = normalize_funnel_language(user.get("language_code"))
            set_chat_mini_app_menu(client, chat_id, language, enabled=True)
            if text and text.startswith("/start"):
                send_legacy_start_message(client, chat_id, language)
        print(f"telegram_funnel legacy_user telegram_id={user.get('id')}")
        return {"ok": True}

    saved_route, saved_language = get_saved_context(db, user)
    menu_language = normalize_funnel_language(saved_language or user.get("language_code"))
    with httpx.Client(timeout=10) as client:
        set_chat_mini_app_menu(client, chat_id, menu_language, enabled=should_show_mini_app_menu(db, user))
        if handle_custom_emoji_id_message(client, chat_id, message):
            return {"ok": True}

    if text and not text.startswith("/start"):
        if handle_test_access_code_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_trader_id_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_pairs_request_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_quote_request_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_signal_request_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        handle_invalid_trader_id_message(db=db, user=user, chat_id=chat_id, text=text)
        return {"ok": True}

    if not text or not text.startswith("/start"):
        return {"ok": True}

    start_context = parse_start_context(text)
    if start_context is None:
        print(f"telegram_start ignored unsupported_payload text={text!r}")
        return {"ok": True}

    funnel_route, deeplink_language = start_context
    language = normalize_funnel_language(deeplink_language or user.get("language_code"))
    print(
        f"telegram_start language_code={user.get('language_code')} "
        f"funnel_route={funnel_route} deeplink_language={deeplink_language} normalized_language={language}"
    )

    save_start_context(db, user, language, funnel_route)

    node_code = "TEAM-01" if funnel_route == "TEAM" else "BOT-01"

    with httpx.Client(timeout=10) as client:
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        try:
            copy_funnel_node(client=client, chat_id=chat_id, node_code=node_code, language=language, user=user)
        except Exception as error:
            send_funnel_delivery_error(client, chat_id, node_code, error)

    return {"ok": True}


def handle_funnel_callback(
    db: Session,
    user: dict[str, Any],
    chat_id: int,
    data: str,
    language: str,
    client: httpx.Client,
) -> str:
    action = data.removeprefix("funnel:")
    texts = funnel_texts(language)

    if action == "bot_start":
        save_start_context(db, user, language, "BOT")
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        copy_funnel_node(client=client, chat_id=chat_id, node_code="BOT-STEP-01", language=language, user=user)
        return texts["callback_ok"]

    if action == "team_start":
        save_start_context(db, user, language, "TEAM")
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        copy_funnel_node(client=client, chat_id=chat_id, node_code="TEAM-STEP-01", language=language, user=user)
        return texts["callback_ok"]

    if action == "existing_account":
        copy_funnel_node(client=client, chat_id=chat_id, node_code="BOT-EXISTING-ACCOUNT", language=language, user=user)
        return texts["callback_ok"]

    if action == "check_topup":
        return texts["topup_pending"]

    return texts["callback_ok"]


def handle_callback_query(callback_query: dict[str, Any], db: Session) -> None:
    callback_id = callback_query.get("id")
    data = callback_query.get("data")
    user = callback_query.get("from") or {}
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    saved_language = get_saved_language(db, user)
    language = normalize_funnel_language(saved_language or user.get("language_code"))
    print(
        f"telegram_callback data={data} language_code={user.get('language_code')} "
        f"saved_language={saved_language} normalized_language={language}"
    )

    with httpx.Client(timeout=10) as client:
        callback_text = funnel_texts(language)["callback_ok"]
        if data and data.startswith("funnel:") and chat_id is not None:
            try:
                callback_text = handle_funnel_callback(
                    db=db,
                    user=user,
                    chat_id=chat_id,
                    data=data,
                    language=language,
                    client=client,
                )
            except Exception as error:
                callback_text = "\u041e\u0448\u0438\u0431\u043a\u0430 \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0438"
                send_funnel_delivery_error(client, chat_id, data.removeprefix("funnel:"), error)
        elif data == "text_format":
            callback_text = LEGACY_TEXT_FORMAT_TEXTS.get(language, LEGACY_TEXT_FORMAT_TEXTS["en"])["selected"]

        if callback_id:
            client.post(
                telegram_api_url("answerCallbackQuery"),
                json={"callback_query_id": callback_id, "text": callback_text},
            ).raise_for_status()

        if data and data.startswith("funnel:"):
            return

        if data != "text_format" or chat_id is None:
            return

        legacy_text = LEGACY_TEXT_FORMAT_TEXTS.get(language, LEGACY_TEXT_FORMAT_TEXTS["en"])
        client.post(
            telegram_api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": legacy_text["message"],
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": legacy_text["open_mini_app"], "web_app": {"url": settings.telegram_webapp_url}}]
                    ]
                },
            },
        ).raise_for_status()


