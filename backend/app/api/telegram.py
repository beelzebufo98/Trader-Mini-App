import re
from html import escape
from datetime import datetime, timedelta
import random
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models.funnel_session import FunnelSession
from app.models.telegram_user import TelegramUser as TelegramUserModel
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
    "TEAM-01": PROJECT_ROOT / "images" / "bot-start.png",
    "BOT-STEP-01": PROJECT_ROOT / "images" / "BOT-STEP-01.png",
    "TEAM-STEP-01": PROJECT_ROOT / "images" / "TEAM-STEP-01.png",
    "ID-01": PROJECT_ROOT / "images" / "ID-01. Запрос Trader ID  Напоминание 2.png",
    "ID-NOT-FOUND": PROJECT_ROOT / "images" / "Ошибка-1-2.png",
}
BOT_REMINDER_SOURCE_MESSAGE_ID = 6
ID_FORMAT_SOURCE_MESSAGE_ID = 21
TOPUP_SOURCE_MESSAGE_ID = 26
TOPUP_LOW_SOURCE_MESSAGE_ID = 29
TOPUP_NOT_FOUND_SOURCE_MESSAGE_ID = 32
BOT_SUCCESS_SOURCE_MESSAGE_ID = 35
BOT_INTRO_REMINDER_KIND = "BOT-01"
BOT_STEP_REMINDER_KIND = "BOT-STEP-01"
ID_REMINDER_KIND = "ID-01"
ID_FORMAT_REMINDER_KIND = "ID-FORMAT"
ID_NOT_FOUND_REMINDER_KIND = "ID-NOT-FOUND"
TOPUP_REMINDER_KIND = "TOPUP-01"
TOPUP_LOW_REMINDER_KIND = "TOPUP-LOW"
TOPUP_NOT_FOUND_REMINDER_KIND = "TOPUP-NOT-FOUND"
MIN_TOPUP_AMOUNT_USD = 20.0
BOT_REMINDER_DELAYS_SECONDS = (
    (5 * 60, 15 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
)
BOT_STEP_REMINDER_DELAYS_SECONDS = (
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
)
ID_REMINDER_DELAYS_SECONDS = (
    (5 * 60, 15 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
)
ID_FORMAT_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
ID_NOT_FOUND_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
TOPUP_LOW_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
TOPUP_NOT_FOUND_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
TOPUP_REMINDER_DELAYS_SECONDS = (
    (5 * 60, 15 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
)
REMINDER_DELAYS_BY_KIND = {
    BOT_INTRO_REMINDER_KIND: BOT_REMINDER_DELAYS_SECONDS,
    BOT_STEP_REMINDER_KIND: BOT_STEP_REMINDER_DELAYS_SECONDS,
    ID_REMINDER_KIND: ID_REMINDER_DELAYS_SECONDS,
    ID_FORMAT_REMINDER_KIND: ID_FORMAT_REMINDER_DELAYS_SECONDS,
    ID_NOT_FOUND_REMINDER_KIND: ID_NOT_FOUND_REMINDER_DELAYS_SECONDS,
    TOPUP_REMINDER_KIND: TOPUP_REMINDER_DELAYS_SECONDS,
    TOPUP_LOW_REMINDER_KIND: TOPUP_LOW_REMINDER_DELAYS_SECONDS,
    TOPUP_NOT_FOUND_REMINDER_KIND: TOPUP_NOT_FOUND_REMINDER_DELAYS_SECONDS,
}
REMINDER_WORKER_POLL_SECONDS = 15
REMINDER_WORKER_BATCH_SIZE = 20
POCKET_ACCOUNT_CLOSE_INSTRUCTION_URL = "https://pocketoption.com/blog/en/interesting/trading-platforms/how-to-close-pocket-option-account/"
_reminder_worker_lock = threading.Lock()
_reminder_worker_started = False


@dataclass(frozen=True)
class FunnelDelivery:
    text_message_id: int | None = None
    media_message_id: int | None = None


PREMIUM_EMOJI = {
    "wave": '<tg-emoji emoji-id="5321095945780209338">\U0001f44b</tg-emoji>',
    "tool": '<tg-emoji emoji-id="5462921117423384478">\U0001f6e0</tg-emoji>',
    "warning": '<tg-emoji emoji-id="5958289678837746828">\u26a0\ufe0f</tg-emoji>',
    "rocket": '<tg-emoji emoji-id="5188481279963715781">\U0001f680</tg-emoji>',
    "money": '<tg-emoji emoji-id="5417924076503062111">\U0001f4b0</tg-emoji>',
    "pick": '<tg-emoji emoji-id="5197371802136892976">\u26cf\ufe0f</tg-emoji>',
    "chart": '<tg-emoji emoji-id="5298614648138919107">\U0001f4c8</tg-emoji>',
    "step_rocket": '<tg-emoji emoji-id="5445284980978621387">\U0001f680</tg-emoji>',
    "step_diamond": '<tg-emoji emoji-id="5427168083074628963">\U0001f48e</tg-emoji>',
    "step_one_blue": '<tg-emoji emoji-id="6084545344924813749">1\ufe0f\u20e3</tg-emoji>',
    "step_two_purple": '<tg-emoji emoji-id="6084472459329800521">2\ufe0f\u20e3</tg-emoji>',
    "step_heart": '<tg-emoji emoji-id="5296278100030536646">\u2763\ufe0f</tg-emoji>',
    "step_one_purple": '<tg-emoji emoji-id="5258124771668794894">1\ufe0f\u20e3</tg-emoji>',
    "step_link": '<tg-emoji emoji-id="5235579174072112613">\U0001f517</tg-emoji>',
    "step_ru": '<tg-emoji emoji-id="5449408995691341691">\U0001f1f7\U0001f1fa</tg-emoji>',
    "step_world": '<tg-emoji emoji-id="5399898266265475100">\U0001f30d</tg-emoji>',
    "step_tv": '<tg-emoji emoji-id="5100437323728815275">\U0001f4fa</tg-emoji>',
    "step_bang": '<tg-emoji emoji-id="5440660757194744323">\u203c\ufe0f</tg-emoji>',
    "step_key": '<tg-emoji emoji-id="5330115548900501467">\U0001f511</tg-emoji>',
    "step_check": '<tg-emoji emoji-id="5206607081334906820">\u2714\ufe0f</tg-emoji>',
    "step_done": '<tg-emoji emoji-id="5021905410089550576">\u2705</tg-emoji>',
    "existing_bang": '<tg-emoji emoji-id="5467890025217661107">\u203c\ufe0f</tg-emoji>',
    "existing_one": '<tg-emoji emoji-id="5258124771668794894">1\ufe0f\u20e3</tg-emoji>',
    "existing_two": '<tg-emoji emoji-id="5258326935779418457">2\ufe0f\u20e3</tg-emoji>',
    "existing_link": '<tg-emoji emoji-id="5235579174072112613">\U0001f517</tg-emoji>',
    "existing_ru": '<tg-emoji emoji-id="5449408995691341691">\U0001f1f7\U0001f1fa</tg-emoji>',
    "existing_world": '<tg-emoji emoji-id="5399898266265475100">\U0001f30d</tg-emoji>',
    "existing_three": '<tg-emoji emoji-id="5255836533352572170">3\ufe0f\u20e3</tg-emoji>',
    "existing_rocket": '<tg-emoji emoji-id="5445284980978621387">\U0001f680</tg-emoji>',
    "id_arrow": '<tg-emoji emoji-id="5215480011322042129">\u27a1\ufe0f</tg-emoji>',
    "id_question": '<tg-emoji emoji-id="5314504236132747481">\u2049\ufe0f</tg-emoji>',
    "id_one": '<tg-emoji emoji-id="6084545344924813749">1\ufe0f\u20e3</tg-emoji>',
    "id_two": '<tg-emoji emoji-id="6084472459329800521">2\ufe0f\u20e3</tg-emoji>',
    "id_three": '<tg-emoji emoji-id="6084542458706791202">3\ufe0f\u20e3</tg-emoji>',
    "id_search": '<tg-emoji emoji-id="5188217332748527444">\U0001f50d</tg-emoji>',
    "not_found_cross": '<tg-emoji emoji-id="5298742255912235479">\u274c</tg-emoji>',
    "not_found_gear": '<tg-emoji emoji-id="5818705028424141605">\u2699\ufe0f</tg-emoji>',
    "not_found_link": '<tg-emoji emoji-id="5235579174072112613">\U0001f517</tg-emoji>',
    "not_found_ru": '<tg-emoji emoji-id="5197708450263476950">\U0001f1f7\U0001f1fa</tg-emoji>',
    "not_found_world": '<tg-emoji emoji-id="5399898266265475100">\U0001f30d</tg-emoji>',
    "team_step_fire": '<tg-emoji emoji-id="4994791135521015443">\U0001f525</tg-emoji>',
    "team_step_alarm": '<tg-emoji emoji-id="5395695537687123235">\U0001f6a8</tg-emoji>',
    "team_step_diamond": '<tg-emoji emoji-id="5462902520215002477">\U0001f48e</tg-emoji>',
    "team_step_one_blue": '<tg-emoji emoji-id="6084545344924813749">1\ufe0f\u20e3</tg-emoji>',
    "team_step_two_purple": '<tg-emoji emoji-id="6084472459329800521">2\ufe0f\u20e3</tg-emoji>',
    "team_step_heart": '<tg-emoji emoji-id="5296278100030536646">\u2763\ufe0f</tg-emoji>',
    "team_step_one": '<tg-emoji emoji-id="5258124771668794894">1\u20e3</tg-emoji>',
    "team_step_link": '<tg-emoji emoji-id="5235579174072112613">\U0001f517</tg-emoji>',
    "team_step_ru": '<tg-emoji emoji-id="5449408995691341691">\U0001f1f7\U0001f1fa</tg-emoji>',
    "team_step_world": '<tg-emoji emoji-id="5399898266265475100">\U0001f30d</tg-emoji>',
    "team_step_tv": '<tg-emoji emoji-id="5100437323728815275">\U0001f4fa</tg-emoji>',
    "team_step_bang": '<tg-emoji emoji-id="5440660757194744323">\u203c</tg-emoji>',
    "team_step_key": '<tg-emoji emoji-id="5330115548900501467">\U0001f511</tg-emoji>',
    "team_step_check": '<tg-emoji emoji-id="5206607081334906820">\u2714</tg-emoji>',
    "team_step_play": '<tg-emoji emoji-id="5348125953090403204">\u25b6\ufe0f</tg-emoji>',
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
        "get_bot": "\U0001f525 \u041f\u041e\u041b\u0423\u0427\u0418\u0422\u042c \u0411\u041e\u0422\u0410",
        "want_team": "\U0001f525 \u0425\u041e\u0427\u0423 \u0412 \u041a\u041e\u041c\u0410\u041d\u0414\u0423",
        "join_team_start": "\U0001f525 \u0412\u0421\u0422\u0423\u041f\u0418\u0422\u042c \u0412 \u041a\u041e\u041c\u0410\u041d\u0414\u0423",
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
        "get_bot": "\U0001f525 GET THE BOT",
        "want_team": "\U0001f525 I WANT TO JOIN THE TEAM",
        "join_team_start": "\U0001f525 JOIN THE TEAM",
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
            f"<tg-spoiler>{PREMIUM_EMOJI['tool']} <i>\u0414\u0430\u0436\u0435 <b>\u0441\u0430\u043c\u044b\u0439 \u0441\u0438\u043b\u044c\u043d\u044b\u0439</b> \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442 \u043e\u0441\u0442\u0430\u0451\u0442\u0441\u044f \u0442\u043e\u043b\u044c\u043a\u043e <b>\u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u043e\u043c</b>.</i></tg-spoiler>\n\n"
            f"<tg-spoiler>{PREMIUM_EMOJI['warning']} <b>\u041d\u041e!</b> \u041c\u044b \u0441\u043e\u0437\u0434\u0430\u043b\u0438 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442, \u043a\u043e\u0442\u043e\u0440\u044b\u0439 <u>\u043c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u043e \u043e\u0431\u043b\u0435\u0433\u0447\u0438\u0442 \u0442\u0432\u043e\u0439 \u043f\u0443\u0442\u044c</u> "
            "\u043d\u0430 \u043f\u0443\u0442\u0438 \u043a \u0431\u043e\u043b\u044c\u0448\u043e\u043c\u0443 \u0437\u0430\u0440\u0430\u0431\u043e\u0442\u043a\u0443 \u043d\u0430 \u0442\u0440\u0435\u0439\u0434\u0438\u043d\u0433\u0435.</tg-spoiler>\n\n"
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
    "BOT-STEP-01": {
        "ru": (
            f"{PREMIUM_EMOJI['step_rocket']} <b>PARADOX BOT</b> — рабочий инструмент для тех, кто хочет "
            "быстрее анализировать рынок, находить торговые ситуации и "
            "<b>принимать решения по системе</b>, а не на эмоциях.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_diamond']} <b>Внутри ты получишь два типа прогнозов:</b></blockquote>\n"
            f"<blockquote>{PREMIUM_EMOJI['step_one_blue']} <i>Алгоритмический прогноз по FOREX и OTC-активам.</i>\n\n"
            f"{PREMIUM_EMOJI['step_two_purple']} <i>Торговую модель с направлением, активом, экспирацией "
            "и параметрами входа.</i></blockquote>\n\n"
            "Каждый прогноз собирается на основе рыночного контекста и "
            "системы из <b>более чем 30 индикаторов.</b>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_heart']} <b>Что будет доступно после подключения:</b></blockquote>\n"
            "<blockquote>• аналитика рынка;\n"
            "• готовые параметры торговой ситуации;\n"
            "• торговая пара и направление;\n"
            "• время экспирации;\n"
            "• системный подход без ручного перебора десятков графиков.</blockquote>\n\n"
            "Чтобы система смогла найти твой аккаунт и открыть доступ к боту, "
            "регистрацию необходимо пройти по нашей ссылке.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_one_purple']} <b>СОЗДАЙ АККАУНТ</b></blockquote>\n"
            "<blockquote>Нажми кнопку регистрации ниже и заполни данные.</blockquote>\n"
            "<blockquote>Это займёт около одной минуты.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['step_link']} <b>РЕГИСТРАЦИЯ:</b>\n\n"
            f"{PREMIUM_EMOJI['step_ru']} ОТКРЫТЬ АККАУНТ ДЛЯ РОССИИ\n"
            f"{PREMIUM_EMOJI['step_world']} ОТКРЫТЬ АККАУНТ ДЛЯ ДРУГИХ СТРАН\n\n"
            f"{PREMIUM_EMOJI['step_bang']}{PREMIUM_EMOJI['step_bang']}{PREMIUM_EMOJI['step_bang']} <b>ВАЖНО</b>\n\n"
            "Если у тебя уже есть аккаунт, нажимай на кнопку\n"
            f"<blockquote>{PREMIUM_EMOJI['step_key']} <b>У МЕНЯ УЖЕ ЕСТЬ АККАУНТ</b></blockquote>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_check']}{PREMIUM_EMOJI['step_check']}{PREMIUM_EMOJI['step_check']} "
            "<b>После регистрации:</b></blockquote>\n"
            "<blockquote>Вернись в этот чат.\n\n"
            "Отправь свой <b>Trader ID.</b></blockquote>\n\n"
            "Дождись автоматической проверки.\n\n"
            "После подтверждения регистрации тебе откроется следующий этап подключения к <b>Paradox Bot.</b>"
        ),
        "en": (
            f"{PREMIUM_EMOJI['step_rocket']} <b>PARADOX BOT</b> is a working tool for anyone who wants to "
            "analyze the market faster, find trading situations, and make decisions by system, not emotion.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_diamond']} <b>Inside you get two forecast types:</b></blockquote>\n"
            f"<blockquote>{PREMIUM_EMOJI['step_one_blue']} <i>Algorithmic forecast for FOREX and OTC assets.</i>\n\n"
            f"{PREMIUM_EMOJI['step_two_purple']} <i>A trading model with direction, asset, expiration, and entry parameters.</i></blockquote>\n\n"
            "Each forecast is built from market context and a system of <b>30+ indicators.</b>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_heart']} <b>After activation you will get:</b></blockquote>\n"
            "<blockquote>• market analytics;\n"
            "• prepared trading situation parameters;\n"
            "• trading pair and direction;\n"
            "• expiration time;\n"
            "• a systematic approach without checking dozens of charts manually.</blockquote>\n\n"
            "To let the system find your account and open bot access, registration must be completed through our link.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_one_purple']} <b>CREATE ACCOUNT</b></blockquote>\n"
            "<blockquote>Tap a registration button below and fill in your details.</blockquote>\n"
            "<blockquote>It takes about one minute.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['step_link']} <b>REGISTRATION:</b>\n\n"
            f"{PREMIUM_EMOJI['step_ru']} OPEN ACCOUNT FOR RUSSIA\n"
            f"{PREMIUM_EMOJI['step_world']} OPEN ACCOUNT FOR OTHER COUNTRIES\n\n"
            f"{PREMIUM_EMOJI['step_bang']}{PREMIUM_EMOJI['step_bang']}{PREMIUM_EMOJI['step_bang']} <b>IMPORTANT</b>\n\n"
            "If you already have an account, tap\n"
            f"<blockquote>{PREMIUM_EMOJI['step_key']} <b>I ALREADY HAVE AN ACCOUNT</b></blockquote>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['step_check']}{PREMIUM_EMOJI['step_check']}{PREMIUM_EMOJI['step_check']} "
            "<b>After registration:</b></blockquote>\n"
            "<blockquote>Return to this chat.\n\n"
            "Send your <b>Trader ID.</b></blockquote>\n\n"
            "Wait for automatic verification.\n\n"
            "After registration is confirmed, the next Paradox Bot activation step will open."
        ),
    },
    "TEAM-STEP-01": {
        "ru": (
            f"{PREMIUM_EMOJI['team_step_fire']} <b>КОМАНДА PARADOX</b> — закрытое пространство для тех, кто хочет "
            "не только использовать готовый инструмент, но и следить за торговыми ситуациями, получать сигналы "
            "и видеть результаты закрытых сделок.\n\n"
            f"{PREMIUM_EMOJI['team_step_alarm']} После подключения ты получишь доступ к <b>Paradox Bot</b> — "
            "сигнально-аналитическому инструменту, который помогает быстрее анализировать рынок и находить "
            "торговые ситуации по системе, а не на эмоциях.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_diamond']} <b>Внутри ты получишь два типа прогнозов:</b></blockquote>\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_one_blue']} <i>Алгоритмический прогноз по <b>FOREX и OTC-активам</b>.</i>\n\n"
            f"{PREMIUM_EMOJI['team_step_two_purple']} <i>Торговую модель с направлением, активом, экспирацией "
            "и параметрами входа.</i></blockquote>\n\n"
            "Каждый прогноз формируется на основе рыночного контекста и системы из <b>более чем 30 индикаторов.</b>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_heart']} <b>Что будет доступно внутри команды:</b>\n"
            "• полный доступ к Paradox Bot;\n"
            "• торговые сигналы по FOREX и OTC-активам;\n"
            "• торговая пара, направление и время экспирации;\n"
            "• готовые параметры торговой ситуации;\n"
            "• рабочие торговые сессии;\n"
            "• результаты и разборы закрытых сделок;\n"
            "• материалы, инструкции и обновления;\n"
            "• доступ в закрытую VIP-группу.</blockquote>\n\n"
            "Чтобы система смогла найти твой аккаунт и открыть доступ к команде, боту и сигналам, "
            "регистрацию необходимо пройти по нашей ссылке.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_one']} <b>СОЗДАЙ АККАУНТ</b></blockquote>\n"
            "<blockquote>Нажми кнопку регистрации ниже и заполни данные.</blockquote>\n"
            "<blockquote>Это займёт около одной минуты.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['team_step_link']} <b>РЕГИСТРАЦИЯ:</b>\n\n"
            f"{PREMIUM_EMOJI['team_step_ru']} ОТКРЫТЬ АККАУНТ ДЛЯ РОССИИ\n"
            f"{PREMIUM_EMOJI['team_step_world']} ОТКРЫТЬ АККАУНТ ДЛЯ ДРУГИХ СТРАН\n\n"
            "<blockquote><b>ПОСМОТРИ КОРОТКУЮ ВИДЕОИНСТРУКЦИЮ</b></blockquote>\n"
            "<blockquote>В видео показан весь процесс регистрации и где найти личный ID аккаунта.</blockquote>\n"
            f"{PREMIUM_EMOJI['team_step_tv']} <b>Видео займёт меньше минуты.</b>\n\n"
            f"{PREMIUM_EMOJI['team_step_bang']}{PREMIUM_EMOJI['team_step_bang']}{PREMIUM_EMOJI['team_step_bang']} <b>ВАЖНО</b>\n\n"
            "Если у тебя уже есть аккаунт, <b>нажимай</b> на кнопку\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_key']} <b>У МЕНЯ УЖЕ ЕСТЬ АККАУНТ</b></blockquote>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_check']}{PREMIUM_EMOJI['team_step_check']}{PREMIUM_EMOJI['team_step_check']}"
            "<b>После регистрации:</b></blockquote>\n"
            "<blockquote>Вернись в этот чат.\n\n"
            "Отправь свой <b>Trader ID.</b>\n\n"
            "Дождись автоматической проверки.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['team_step_play']} После подтверждения регистрации тебе откроется следующий этап "
            "подключения к <b>команде Paradox, Paradox Bot, торговым сигналам и закрытой VIP-группе.</b>"
        ),
        "en": (
            f"{PREMIUM_EMOJI['team_step_fire']} <b>PARADOX TEAM</b> is a closed space for those who want to use the tool, "
            "track trading situations, receive signals, and see closed trade results.\n\n"
            f"{PREMIUM_EMOJI['team_step_alarm']} After connection you will get access to <b>Paradox Bot</b>, "
            "a signal and analytics tool for faster market analysis.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_diamond']} <b>Inside you get two forecast types:</b></blockquote>\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_one_blue']} <i>Algorithmic forecast for <b>FOREX and OTC assets</b>.</i>\n\n"
            f"{PREMIUM_EMOJI['team_step_two_purple']} <i>A trading model with direction, asset, expiration, and entry parameters.</i></blockquote>\n\n"
            "Each forecast is based on market context and a system of <b>30+ indicators.</b>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_heart']} <b>Inside the team you will get:</b>\n"
            "• full access to Paradox Bot;\n"
            "• trading signals for FOREX and OTC assets;\n"
            "• pair, direction, and expiration time;\n"
            "• ready trading situation parameters;\n"
            "• working trading sessions;\n"
            "• results and breakdowns of closed trades;\n"
            "• materials, instructions, and updates;\n"
            "• access to a closed VIP group.</blockquote>\n\n"
            "To find your account and open team access, register through our link.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_one']} <b>CREATE ACCOUNT</b></blockquote>\n"
            "<blockquote>Tap a registration button below and fill in your details.</blockquote>\n"
            "<blockquote>It takes about one minute.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['team_step_link']} <b>REGISTRATION:</b>\n\n"
            f"{PREMIUM_EMOJI['team_step_ru']} OPEN ACCOUNT FOR RUSSIA\n"
            f"{PREMIUM_EMOJI['team_step_world']} OPEN ACCOUNT FOR OTHER COUNTRIES\n\n"
            "<blockquote><b>WATCH THE SHORT VIDEO INSTRUCTION</b></blockquote>\n"
            "<blockquote>The video shows the full registration process and where to find your account ID.</blockquote>\n"
            f"{PREMIUM_EMOJI['team_step_tv']} <b>The video takes less than a minute.</b>\n\n"
            f"{PREMIUM_EMOJI['team_step_bang']}{PREMIUM_EMOJI['team_step_bang']}{PREMIUM_EMOJI['team_step_bang']} <b>IMPORTANT</b>\n\n"
            "If you already have an account, tap\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_key']} <b>I ALREADY HAVE AN ACCOUNT</b></blockquote>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['team_step_check']}{PREMIUM_EMOJI['team_step_check']}{PREMIUM_EMOJI['team_step_check']}"
            "<b>After registration:</b></blockquote>\n"
            "<blockquote>Return to this chat.\n\n"
            "Send your <b>Trader ID.</b>\n\n"
            "Wait for automatic verification.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['team_step_play']} After registration is confirmed, the next connection step will open for "
            "<b>the Paradox team, Paradox Bot, trading signals, and the closed VIP group.</b>"
        ),
    },
    "ID-01": {
        "ru": (
            f"<blockquote>{PREMIUM_EMOJI['id_arrow']} {PREMIUM_EMOJI['id_arrow']} {PREMIUM_EMOJI['id_arrow']} "
            "<b>ДАВАЙ ПРОДОЛЖИМ</b></blockquote>\n\n"
            "После <i>регистрации</i> в торговом профиле отображается личный номер аккаунта — <b>Trader ID.</b>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['id_question']} <b>Что нужно сделать:</b></blockquote>\n"
            f"<blockquote>{PREMIUM_EMOJI['id_one']} <i>Открой торговый профиль.</i>\n\n"
            f"{PREMIUM_EMOJI['id_two']} <i>Найди номер аккаунта.</i>\n\n"
            f"{PREMIUM_EMOJI['id_three']} <i>Отправь Trader ID сюда одним сообщением.</i></blockquote>\n\n"
            "<b>Подойдут варианты:</b>\n"
            "<blockquote><code>123456</code>\n"
            "<code>ID123456</code>\n"
            "<code>ID 123456</code></blockquote>\n\n"
            f"{PREMIUM_EMOJI['id_search']} После отправки бот автоматически проверит аккаунт в партнёрской базе."
        ),
        "en": (
            f"<blockquote>{PREMIUM_EMOJI['id_arrow']} {PREMIUM_EMOJI['id_arrow']} {PREMIUM_EMOJI['id_arrow']} "
            "<b>LET'S CONTINUE</b></blockquote>\n\n"
            "After <i>registration</i>, your trading profile shows your personal account number — <b>Trader ID.</b>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['id_question']} <b>What to do:</b></blockquote>\n"
            f"<blockquote>{PREMIUM_EMOJI['id_one']} <i>Open your trading profile.</i>\n\n"
            f"{PREMIUM_EMOJI['id_two']} <i>Find your account number.</i>\n\n"
            f"{PREMIUM_EMOJI['id_three']} <i>Send Trader ID here as one message.</i></blockquote>\n\n"
            "<b>Accepted formats:</b>\n"
            "<blockquote><code>123456</code>\n"
            "<code>ID123456</code>\n"
            "<code>ID 123456</code></blockquote>\n\n"
            f"{PREMIUM_EMOJI['id_search']} After you send it, the bot will automatically check the account in the partner database."
        ),
    },
    "BOT-EXISTING-ACCOUNT": {
        "ru": (
            f"{PREMIUM_EMOJI['existing_bang']} <b>ЕСЛИ У ТЕБЯ УЖЕ ЕСТЬ АККАУНТ</b>\n\n"
            "Чтобы система смогла подтвердить регистрацию и открыть доступ, "
            "необходимо пройти повторное подключение.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['existing_one']} <b>УДАЛИ СТАРЫЙ АККАУНТ</b></blockquote>\n"
            f"<blockquote>Выполни удаление по <a href=\"{POCKET_ACCOUNT_CLOSE_INSTRUCTION_URL}\">инструкции</a> "
            "и дождись подтверждения закрытия аккаунта.</blockquote>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['existing_two']} <b>СОЗДАЙ НОВЫЙ АККАУНТ</b></blockquote>\n"
            "<blockquote>После удаления вернись в бот и зарегистрируйся только по нашей ссылке.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['existing_link']} <b>РЕГИСТРАЦИЯ:</b>\n\n"
            f"{PREMIUM_EMOJI['existing_ru']} ОТКРЫТЬ АККАУНТ ДЛЯ РОССИИ\n"
            f"{PREMIUM_EMOJI['existing_world']} ОТКРЫТЬ АККАУНТ ДЛЯ ДРУГИХ СТРАН\n\n"
            f"<blockquote>{PREMIUM_EMOJI['existing_three']} <b>ОТПРАВЬ НОВЫЙ TRADER ID</b></blockquote>\n"
            "<blockquote>Бот проверит регистрацию и откроет следующий этап активации.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['existing_rocket']} После подтверждения ты сможешь продолжить подключение к <b>Paradox Bot.</b>"
        ),
        "en": (
            f"{PREMIUM_EMOJI['existing_bang']} <b>IF YOU ALREADY HAVE AN ACCOUNT</b>\n\n"
            "To confirm registration and open access, you need to reconnect through our partner link.\n\n"
            f"<blockquote>{PREMIUM_EMOJI['existing_one']} <b>DELETE YOUR OLD ACCOUNT</b></blockquote>\n"
            f"<blockquote>Follow the <a href=\"{POCKET_ACCOUNT_CLOSE_INSTRUCTION_URL}\">instruction</a> "
            "and wait until account closure is confirmed.</blockquote>\n\n"
            f"<blockquote>{PREMIUM_EMOJI['existing_two']} <b>CREATE A NEW ACCOUNT</b></blockquote>\n"
            "<blockquote>After deletion, return to the bot and register only through our link.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['existing_link']} <b>REGISTRATION:</b>\n\n"
            f"{PREMIUM_EMOJI['existing_ru']} OPEN ACCOUNT FOR RUSSIA\n"
            f"{PREMIUM_EMOJI['existing_world']} OPEN ACCOUNT FOR OTHER COUNTRIES\n\n"
            f"<blockquote>{PREMIUM_EMOJI['existing_three']} <b>SEND YOUR NEW TRADER ID</b></blockquote>\n"
            "<blockquote>The bot will verify registration and open the next activation step.</blockquote>\n\n"
            f"{PREMIUM_EMOJI['existing_rocket']} After confirmation, you will continue connecting to <b>Paradox Bot.</b>"
        ),
    },
    "ID-FORMAT": {
        "ru": "\u041f\u0440\u0438\u0448\u043b\u0438 Trader ID \u0432 \u0444\u043e\u0440\u043c\u0430\u0442\u0435 <code>123456</code> \u0438\u043b\u0438 <code>ID123456</code>.",
        "en": "Send Trader ID as <code>123456</code> or <code>ID123456</code>.",
    },
    "ID-NOT-FOUND": {
        "ru": (
            f"<blockquote>{PREMIUM_EMOJI['not_found_cross']} <b>АККАУНТ НЕ НАЙДЕН ПО НАШЕЙ ССЫЛКЕ</b></blockquote>\n\n"
            "Система не смогла подтвердить партнёрскую регистрацию.\n\n"
            "<blockquote><i>Возможные причины:</i>\n\n"
            "• <i>регистрация ещё не завершена;</i>\n"
            "• <i>аккаунт создан по другой ссылке;</i>\n"
            "• <i>указан неверный Trader ID;</i>\n"
            "• <i>данные ещё обновляются.</i></blockquote>\n\n"
            f"{PREMIUM_EMOJI['not_found_gear']} Проверь номер и отправь другой Trader ID или повторно "
            "перейди к регистрации.\n\n"
            f"{PREMIUM_EMOJI['not_found_link']} <b>РЕГИСТРАЦИЯ:</b>\n\n"
            f"{PREMIUM_EMOJI['not_found_ru']} ОТКРЫТЬ АККАУНТ ДЛЯ РОССИИ\n"
            f"{PREMIUM_EMOJI['not_found_world']} ОТКРЫТЬ АККАУНТ ДЛЯ ДРУГИХ СТРАН"
        ),
        "en": (
            f"<blockquote>{PREMIUM_EMOJI['not_found_cross']} <b>ACCOUNT WAS NOT FOUND THROUGH OUR LINK</b></blockquote>\n\n"
            "The system could not confirm partner registration.\n\n"
            "<blockquote><i>Possible reasons:</i>\n\n"
            "• <i>registration is not finished yet;</i>\n"
            "• <i>the account was created through another link;</i>\n"
            "• <i>the Trader ID is incorrect;</i>\n"
            "• <i>the data is still updating.</i></blockquote>\n\n"
            f"{PREMIUM_EMOJI['not_found_gear']} Check the number and send another Trader ID or open registration again.\n\n"
            f"{PREMIUM_EMOJI['not_found_link']} <b>REGISTRATION:</b>\n\n"
            f"{PREMIUM_EMOJI['not_found_ru']} OPEN ACCOUNT FOR RUSSIA\n"
            f"{PREMIUM_EMOJI['not_found_world']} OPEN ACCOUNT FOR OTHER COUNTRIES"
        ),
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
FUNNEL_NODE_TEXTS["TEAM-01"] = FUNNEL_NODE_TEXTS["BOT-01"]
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


def upsert_telegram_user(db: Session, user: dict[str, Any]) -> TelegramUserModel | None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return None

    telegram_user = db.query(TelegramUserModel).filter(TelegramUserModel.telegram_id == telegram_id).first()
    if telegram_user is None:
        telegram_user = TelegramUserModel(
            telegram_id=telegram_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
        )
        db.add(telegram_user)
    else:
        telegram_user.username = user.get("username")
        telegram_user.first_name = user.get("first_name")

    return telegram_user


def get_or_create_user_settings(db: Session, telegram_id: int) -> UserSettings:
    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is not None:
        return settings_row

    settings_row = UserSettings(telegram_id=telegram_id)
    db.add(settings_row)
    return settings_row


def get_or_create_funnel_session(db: Session, telegram_id: int) -> FunnelSession:
    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    if funnel_session is not None:
        return funnel_session

    funnel_session = FunnelSession(telegram_id=telegram_id)
    db.add(funnel_session)
    return funnel_session


def save_start_context(db: Session, user: dict[str, Any], language: str, funnel_route: str) -> None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return

    upsert_telegram_user(db, user)
    settings_row = get_or_create_user_settings(db, telegram_id)
    funnel_session = get_or_create_funnel_session(db, telegram_id)
    settings_row.language = language
    funnel_session.route = funnel_route

    db.commit()


def funnel_texts(language: str) -> dict[str, str]:
    return FUNNEL_BUTTON_TEXTS.get(normalize_funnel_language(language), FUNNEL_BUTTON_TEXTS["en"])


def is_funnel_test_user(user: dict[str, Any]) -> bool:
    return settings.telegram_funnel_test_mode_enabled and is_funnel_user_allowed(user)


def has_funnel_access(db: Session, user: dict[str, Any]) -> bool:
    telegram_id = user.get("id")
    if telegram_id is None:
        return False

    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    return bool(funnel_session and funnel_session.access_granted)


def grant_funnel_access(db: Session, user: dict[str, Any]) -> None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return

    upsert_telegram_user(db, user)
    get_or_create_user_settings(db, telegram_id)
    funnel_session = get_or_create_funnel_session(db, telegram_id)
    funnel_session.access_granted = True

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


def copy_source_message(
    client: httpx.Client,
    chat_id: int,
    source_message_id: int,
    language: str,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> int | None:
    if not settings.telegram_source_channel_id:
        print("telegram_source_copy skipped: TELEGRAM_SOURCE_CHANNEL_ID is empty")
        return None

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "from_chat_id": settings.telegram_source_channel_id,
        "message_id": source_message_id,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    response = client.post(telegram_api_url("copyMessage"), json=payload)
    response.raise_for_status()
    result = response.json().get("result") or {}
    message_id = result.get("message_id")
    print(f"telegram_copy_source source_message_id={source_message_id} chat_id={chat_id} copied_message_id={message_id}")
    return message_id if isinstance(message_id, int) else None


def delete_chat_message(client: httpx.Client, chat_id: int, message_id: int | None) -> None:
    if message_id is None:
        return

    try:
        client.post(
            telegram_api_url("deleteMessage"),
            json={"chat_id": chat_id, "message_id": message_id},
        ).raise_for_status()
    except Exception as error:
        print(f"telegram_delete_message_failed chat_id={chat_id} message_id={message_id} detail={telegram_error_detail(error)}")


def delete_funnel_delivery(client: httpx.Client, chat_id: int, text_message_id: int | None, media_message_id: int | None) -> None:
    delete_chat_message(client, chat_id, media_message_id)
    delete_chat_message(client, chat_id, text_message_id)


def get_reminder_delay_seconds(kind: str, stage: int) -> int | None:
    reminder_delays = REMINDER_DELAYS_BY_KIND.get(kind)
    if reminder_delays is None or stage < 1 or stage > len(reminder_delays):
        return None

    delay_min, delay_max = reminder_delays[stage - 1]
    return random.randint(delay_min, delay_max)


def schedule_bot_reminder_row(funnel_session: FunnelSession, chat_id: int, stage: int, kind: str) -> bool:
    delay_seconds = get_reminder_delay_seconds(kind, stage)
    if delay_seconds is None:
        return False

    funnel_session.reminder_chat_id = chat_id
    funnel_session.reminder_due_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    print(
        "telegram_bot_reminder_scheduled "
        f"telegram_id={funnel_session.telegram_id} kind={kind} stage={stage} delay_seconds={delay_seconds}"
    )
    return True


def start_bot_reminder_flow(
    db: Session,
    user: dict[str, Any],
    chat_id: int,
    language: str,
    kind: str = BOT_INTRO_REMINDER_KIND,
    initial_message_id: int | None = None,
    initial_media_message_id: int | None = None,
) -> None:
    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return

    if kind not in REMINDER_DELAYS_BY_KIND:
        return

    get_or_create_user_settings(db, telegram_id)
    funnel_session = get_or_create_funnel_session(db, telegram_id)

    token = uuid.uuid4().hex
    funnel_session.reminder_kind = kind
    funnel_session.reminder_stage = 1
    funnel_session.reminder_token = token
    funnel_session.last_reminder_message_id = initial_message_id
    funnel_session.last_media_message_id = initial_media_message_id
    if not schedule_bot_reminder_row(funnel_session, chat_id, stage=1, kind=kind):
        return
    db.commit()


def cancel_bot_reminder_flow(db: Session, user: dict[str, Any], client: httpx.Client | None = None, chat_id: int | None = None) -> None:
    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return

    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    if funnel_session is None:
        return

    last_message_id = funnel_session.last_reminder_message_id
    last_media_message_id = funnel_session.last_media_message_id
    funnel_session.reminder_kind = ""
    funnel_session.reminder_stage = 0
    funnel_session.reminder_token = ""
    funnel_session.reminder_chat_id = None
    funnel_session.reminder_due_at = None
    funnel_session.last_reminder_message_id = None
    funnel_session.last_media_message_id = None
    db.commit()

    if client is not None and chat_id is not None:
        delete_funnel_delivery(client, chat_id, last_message_id, last_media_message_id)


def run_bot_reminder_stage(chat_id: int, telegram_id: int, token: str, language: str, stage: int, kind: str) -> None:
    db = SessionLocal()
    try:
        funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
        if funnel_session is None:
            return
        if (
            funnel_session.reminder_kind != kind
            or funnel_session.reminder_token != token
            or funnel_session.reminder_stage != stage
        ):
            return
        if funnel_session.access_granted:
            cancel_bot_reminder_flow(db, {"id": telegram_id})
            return

        reminder_delays = REMINDER_DELAYS_BY_KIND.get(kind)
        if reminder_delays is None:
            cancel_bot_reminder_flow(db, {"id": telegram_id})
            return

        telegram_user = db.query(TelegramUserModel).filter(TelegramUserModel.telegram_id == telegram_id).first()
        user = {
            "id": telegram_id,
            "username": telegram_user.username if telegram_user else None,
            "first_name": telegram_user.first_name if telegram_user else None,
        }
        with httpx.Client(timeout=20) as client:
            delete_funnel_delivery(
                client,
                chat_id,
                funnel_session.last_reminder_message_id,
                funnel_session.last_media_message_id,
            )

            if kind == BOT_INTRO_REMINDER_KIND and stage < len(reminder_delays):
                message_id = copy_source_message(
                    client=client,
                    chat_id=chat_id,
                    source_message_id=BOT_REMINDER_SOURCE_MESSAGE_ID,
                    language=language,
                    reply_markup=bot_reminder_keyboard(language),
                )
                funnel_session.last_reminder_message_id = message_id
                funnel_session.last_media_message_id = None
                funnel_session.reminder_stage = stage + 1
                schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                db.commit()
                return

            if kind == BOT_INTRO_REMINDER_KIND:
                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="BOT-STEP-01", language=language, user=user)
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=BOT_STEP_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
                return

            if kind == ID_REMINDER_KIND:
                delivery = copy_funnel_node(
                    client=client,
                    chat_id=chat_id,
                    node_code="ID-01",
                    language=language,
                    user=user,
                )
                funnel_session.last_reminder_message_id = delivery.text_message_id
                funnel_session.last_media_message_id = delivery.media_message_id
                if stage < len(reminder_delays):
                    funnel_session.reminder_stage = stage + 1
                    schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                    db.commit()
                    return

                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                return

            if kind in {ID_FORMAT_REMINDER_KIND, ID_NOT_FOUND_REMINDER_KIND}:
                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                delivery = copy_funnel_node(
                    client=client,
                    chat_id=chat_id,
                    node_code="ID-01",
                    language=language,
                    user=user,
                )
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=ID_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
                return

            if kind == TOPUP_REMINDER_KIND:
                delivery = send_topup_step(client=client, chat_id=chat_id, language=language, user=user)
                funnel_session.last_reminder_message_id = delivery.text_message_id
                funnel_session.last_media_message_id = delivery.media_message_id
                if stage < len(reminder_delays):
                    funnel_session.reminder_stage = stage + 1
                    schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                    db.commit()
                    return

                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                return

            if kind in {TOPUP_LOW_REMINDER_KIND, TOPUP_NOT_FOUND_REMINDER_KIND}:
                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                copy_funnel_node(
                    client=client,
                    chat_id=chat_id,
                    node_code="REMINDER-03",
                    language=language,
                    user=user,
                )
                return

            if kind == BOT_STEP_REMINDER_KIND:
                step_node_code = "TEAM-STEP-01" if funnel_session.route == "TEAM" else "BOT-STEP-01"
                delivery = copy_funnel_node(
                    client=client,
                    chat_id=chat_id,
                    node_code=step_node_code,
                    language=language,
                    user=user,
                )
                funnel_session.last_reminder_message_id = delivery.text_message_id
                funnel_session.last_media_message_id = delivery.media_message_id
                if stage < len(reminder_delays):
                    funnel_session.reminder_stage = stage + 1
                    schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                    db.commit()
                    return

                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                db.commit()
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=ID_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
    except Exception as error:
        print(f"telegram_bot_reminder_failed telegram_id={telegram_id} kind={kind} stage={stage} detail={telegram_error_detail(error)}")
    finally:
        db.close()


def process_due_funnel_reminders() -> None:
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        due_rows = (
            db.query(FunnelSession)
            .filter(
                FunnelSession.reminder_kind != "",
                FunnelSession.reminder_stage > 0,
                FunnelSession.reminder_token != "",
                FunnelSession.reminder_chat_id.isnot(None),
                FunnelSession.reminder_due_at.isnot(None),
                FunnelSession.reminder_due_at <= now,
            )
            .order_by(FunnelSession.reminder_due_at.asc())
            .limit(REMINDER_WORKER_BATCH_SIZE)
            .all()
        )
        jobs = [
            {
                "chat_id": row.reminder_chat_id,
                "telegram_id": row.telegram_id,
                "token": row.reminder_token,
                "language": normalize_funnel_language(
                    (
                        db.query(UserSettings.language)
                        .filter(UserSettings.telegram_id == row.telegram_id)
                        .scalar()
                    )
                ),
                "stage": row.reminder_stage,
                "kind": row.reminder_kind,
            }
            for row in due_rows
            if row.reminder_chat_id is not None
        ]
    finally:
        db.close()

    for job in jobs:
        run_bot_reminder_stage(
            chat_id=int(job["chat_id"]),
            telegram_id=int(job["telegram_id"]),
            token=str(job["token"]),
            language=str(job["language"]),
            stage=int(job["stage"]),
            kind=str(job["kind"]),
        )


def run_funnel_reminder_worker() -> None:
    print("telegram_funnel_reminder_worker_started")
    while True:
        try:
            process_due_funnel_reminders()
        except Exception as error:
            print(f"telegram_funnel_reminder_worker_failed detail={telegram_error_detail(error)}")
        time.sleep(REMINDER_WORKER_POLL_SECONDS)


def start_funnel_reminder_worker() -> None:
    global _reminder_worker_started

    if not settings.telegram_funnel_enabled:
        print("telegram_funnel_reminder_worker_skipped disabled")
        return

    with _reminder_worker_lock:
        if _reminder_worker_started:
            return

        worker = threading.Thread(target=run_funnel_reminder_worker, daemon=True)
        worker.start()
        _reminder_worker_started = True


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
        return {"inline_keyboard": [[{"text": texts["join_team_start"], "callback_data": "funnel:team_start"}]]}

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


def bot_reminder_keyboard(language: str) -> dict[str, Any]:
    texts = funnel_texts(language)
    return {"inline_keyboard": [[{"text": texts["get_bot"], "callback_data": "funnel:bot_start"}]]}


def send_topup_step(client: httpx.Client, chat_id: int, language: str, user: dict[str, Any] | None = None) -> FunnelDelivery:
    message_id = copy_source_message(
        client=client,
        chat_id=chat_id,
        source_message_id=TOPUP_SOURCE_MESSAGE_ID,
        language=language,
        reply_markup=funnel_node_keyboard("TOPUP-01", language),
    )
    if message_id is not None:
        return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code="TOPUP-01", language=language, user=user)


def send_topup_low(client: httpx.Client, chat_id: int, language: str, user: dict[str, Any] | None = None) -> FunnelDelivery:
    message_id = copy_source_message(
        client=client,
        chat_id=chat_id,
        source_message_id=TOPUP_LOW_SOURCE_MESSAGE_ID,
        language=language,
        reply_markup=funnel_node_keyboard("TOPUP-LOW", language),
    )
    if message_id is not None:
        return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code="TOPUP-LOW", language=language, user=user)


def send_topup_not_found(client: httpx.Client, chat_id: int, language: str, user: dict[str, Any] | None = None) -> FunnelDelivery:
    message_id = copy_source_message(
        client=client,
        chat_id=chat_id,
        source_message_id=TOPUP_NOT_FOUND_SOURCE_MESSAGE_ID,
        language=language,
        reply_markup=funnel_node_keyboard("TOPUP-NOT-FOUND", language),
    )
    if message_id is not None:
        return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code="TOPUP-NOT-FOUND", language=language, user=user)


def send_funnel_success(
    client: httpx.Client,
    chat_id: int,
    language: str,
    node_code: str,
    user: dict[str, Any] | None = None,
) -> FunnelDelivery:
    if node_code == "BOT-SUCCESS":
        message_id = copy_source_message(
            client=client,
            chat_id=chat_id,
            source_message_id=BOT_SUCCESS_SOURCE_MESSAGE_ID,
            language=language,
            reply_markup=funnel_node_keyboard("BOT-SUCCESS", language),
        )
        if message_id is not None:
            return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code=node_code, language=language, user=user)


def copy_funnel_node(
    client: httpx.Client,
    chat_id: int,
    node_code: str,
    language: str,
    user: dict[str, Any] | None = None,
) -> FunnelDelivery:
    text_by_language = FUNNEL_NODE_TEXTS.get(node_code)
    if text_by_language is None:
        raise HTTPException(status_code=500, detail=f"Funnel node text is not configured: {node_code}")

    text = text_by_language.get(normalize_funnel_language(language), text_by_language["en"])
    text = text.replace("{\u0438\u043c\u044f}", "{name}").replace("{name}", user_display_name(user, language))
    photo_path = FUNNEL_NODE_PHOTOS.get(node_code)
    media_message_id: int | None = None
    if photo_path is not None and photo_path.exists():
        with photo_path.open("rb") as photo:
            photo_response = client.post(
                telegram_api_url("sendPhoto"),
                data={"chat_id": chat_id},
                files={"photo": (photo_path.name, photo, "image/png")},
            )
            photo_response.raise_for_status()
            photo_result = photo_response.json().get("result") or {}
            photo_message_id = photo_result.get("message_id")
            media_message_id = photo_message_id if isinstance(photo_message_id, int) else None

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
    result = response.json().get("result") or {}
    message_id = result.get("message_id")
    text_message_id = message_id if isinstance(message_id, int) else None
    print(
        f"telegram_send_node node={node_code} chat_id={chat_id} "
        f"message_id={text_message_id} media_message_id={media_message_id}"
    )
    return FunnelDelivery(text_message_id=text_message_id, media_message_id=media_message_id)


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
    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()

    language = settings_row.language if settings_row and settings_row.language in SUPPORTED_LANGUAGES else None
    funnel_route = funnel_session.route if funnel_session and funnel_session.route in {"BOT", "TEAM"} else None
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


def parse_money_amount(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def get_topup_amount(payload: dict[str, Any]) -> float | None:
    total_deposits = parse_money_amount(payload.get("total_deposits"))
    if total_deposits is not None:
        return total_deposits

    return parse_money_amount(payload.get("ftd_amount"))


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
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        set_chat_mini_app_menu(client, chat_id, language, enabled=True)
        send_funnel_success(client=client, chat_id=chat_id, language=language, node_code=node_code, user=user)
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
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        try:
            get_user_info(trader_id)
        except PocketOptionApiError as error:
            if error.status_code == 404:
                delivery = copy_funnel_node(client, chat_id, "ID-NOT-FOUND", language, user=user)
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=ID_NOT_FOUND_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
                return True

            send_html_message(client, chat_id, texts["unavailable"])
            return True
        except (PocketOptionConfigError, PocketOptionRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        telegram_id = user.get("id")
        if isinstance(telegram_id, int):
            funnel_session = get_or_create_funnel_session(db, telegram_id)
            funnel_session.trader_id = trader_id
            db.commit()
        delivery = send_topup_step(client=client, chat_id=chat_id, language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=TOPUP_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return True


def handle_invalid_trader_id_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    if text.startswith("/"):
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route not in {"BOT", "TEAM"}:
        return False

    language = normalize_funnel_language(language or user.get("language_code"))
    with httpx.Client(timeout=10) as client:
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        message_id = copy_source_message(
            client=client,
            chat_id=chat_id,
            source_message_id=ID_FORMAT_SOURCE_MESSAGE_ID,
            language=language,
        )
        if message_id is None:
            delivery = copy_funnel_node(client, chat_id, "ID-FORMAT", language, user=user)
            message_id = delivery.text_message_id
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=ID_FORMAT_REMINDER_KIND,
            initial_message_id=message_id,
        )
    return True


def handle_topup_check_callback(db: Session, user: dict[str, Any], chat_id: int, language: str, client: httpx.Client) -> str:
    texts = TRADER_ID_TEXTS.get(language, TRADER_ID_TEXTS["en"])
    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return texts["unavailable"]

    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    trader_id = funnel_session.trader_id.strip() if funnel_session and funnel_session.trader_id else ""
    if not trader_id:
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="ID-01", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=ID_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return funnel_texts(language)["callback_ok"]

    cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
    try:
        payload = get_user_info(trader_id)
    except PocketOptionApiError as error:
        if error.status_code == 404:
            send_topup_not_found(client=client, chat_id=chat_id, language=language, user=user)
            start_bot_reminder_flow(
                db,
                user,
                chat_id,
                language,
                kind=TOPUP_NOT_FOUND_REMINDER_KIND,
            )
            return funnel_texts(language)["callback_ok"]

        send_html_message(client, chat_id, texts["unavailable"])
        return texts["unavailable"]
    except (PocketOptionConfigError, PocketOptionRequestError):
        send_html_message(client, chat_id, texts["unavailable"])
        return texts["unavailable"]

    topup_amount = get_topup_amount(payload)
    if topup_amount is None or topup_amount <= 0:
        send_topup_not_found(client=client, chat_id=chat_id, language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=TOPUP_NOT_FOUND_REMINDER_KIND,
        )
        return funnel_texts(language)["callback_ok"]

    if topup_amount < MIN_TOPUP_AMOUNT_USD:
        send_topup_low(client=client, chat_id=chat_id, language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=TOPUP_LOW_REMINDER_KIND,
        )
        return funnel_texts(language)["callback_ok"]

    grant_funnel_access(db, user)
    node_code = "TEAM-SUCCESS" if (funnel_session and funnel_session.route == "TEAM") else "BOT-SUCCESS"
    set_chat_mini_app_menu(client, chat_id, language, enabled=True)
    send_funnel_success(client=client, chat_id=chat_id, language=language, node_code=node_code, user=user)
    return funnel_texts(language)["callback_ok"]


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
            delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code=node_code, language=language, user=user)
            if node_code == "BOT-01":
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
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
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="BOT-STEP-01", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=BOT_STEP_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return texts["callback_ok"]

    if action == "team_start":
        save_start_context(db, user, language, "TEAM")
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="TEAM-STEP-01", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=BOT_STEP_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return texts["callback_ok"]

    if action == "existing_account":
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="BOT-EXISTING-ACCOUNT", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=ID_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return texts["callback_ok"]

    if action == "check_topup":
        return handle_topup_check_callback(db=db, user=user, chat_id=chat_id, language=language, client=client)

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


