import re
from html import escape
from pathlib import Path
from typing import Any

from app.config import settings

SUPPORTED_LANGUAGES = {"ru", "en", "es", "pt", "tr", "ar"}
FUNNEL_LANGUAGES = {"ru", "en"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
POCKET_ACCOUNT_CLOSE_INSTRUCTION_URL = "https://pocketoption.com/blog/en/interesting/trading-platforms/how-to-close-pocket-option-account/"
FUNNEL_NODE_PHOTOS = {
    "BOT-01": PROJECT_ROOT / "images" / "bot-start.png",
    "TEAM-01": PROJECT_ROOT / "images" / "bot-start.png",
    "BOT-STEP-01": PROJECT_ROOT / "images" / "BOT-STEP-01.png",
    "TEAM-STEP-01": PROJECT_ROOT / "images" / "TEAM-STEP-01.png",
    "TEAM-SUCCESS": PROJECT_ROOT / "images" / "TEAM-FINAL.png",
    "ID-01": PROJECT_ROOT / "images" / "ID-01. Запрос Trader ID  Напоминание 2.png",
    "ID-NOT-FOUND": PROJECT_ROOT / "images" / "Ошибка-1-2.png",
    "REMINDER-03": PROJECT_ROOT / "images" / "REMIND.png",
}

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
    "team_final_top": '<tg-emoji emoji-id="5415655814079723871">\U0001f51d</tg-emoji>',
    "team_final_shield": '<tg-emoji emoji-id="5251203410396458957">\U0001f6e1</tg-emoji>',
    "team_final_star": '<tg-emoji emoji-id="5438496463044752972">\u2b50\ufe0f</tg-emoji>',
    "team_final_one": '<tg-emoji emoji-id="6084545344924813749">1\ufe0f\u20e3</tg-emoji>',
    "team_final_two": '<tg-emoji emoji-id="6084472459329800521">2\ufe0f\u20e3</tg-emoji>',
    "team_final_chat": '<tg-emoji emoji-id="5443038326535759644">\U0001f4ac</tg-emoji>',
    "team_final_plus": '<tg-emoji emoji-id="5397916757333654639">\u2795</tg-emoji>',
    "team_final_crown": '<tg-emoji emoji-id="5217822164362739968">\U0001f451</tg-emoji>',
    "team_final_candle": '<tg-emoji emoji-id="5451882707875276247">\U0001f56f</tg-emoji>',
    "reminder_03_search": '<tg-emoji emoji-id="5231012545799666522">\U0001f50d</tg-emoji>',
    "reminder_03_link": '<tg-emoji emoji-id="5235579174072112613">\U0001f517</tg-emoji>',
    "reminder_03_hundred": '<tg-emoji emoji-id="5341498088408234504">\U0001f4af</tg-emoji>',
    "reminder_03_heart": '<tg-emoji emoji-id="5296278100030536646">\u2763\ufe0f</tg-emoji>',
    "reminder_03_down": '<tg-emoji emoji-id="5300951660103743368">\U0001f447</tg-emoji>',
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
        "continue_registration": "\U0001f525 \u0425\u041e\u0427\u0423 \u0412 \u041a\u041e\u041c\u0410\u041d\u0414\u0423",
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
        "continue_registration": "\U0001f525 I WANT TO JOIN THE TEAM",
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
        "ru": (
            f"{PREMIUM_EMOJI['team_final_top']}{PREMIUM_EMOJI['team_final_top']} "
            f"<b>ДОСТУП К КОМАНДЕ PARADOX ОТКРЫТ</b> "
            f"{PREMIUM_EMOJI['team_final_top']}{PREMIUM_EMOJI['team_final_top']}\n\n"
            f"Все условия выполнены, а твой аккаунт успешно подтверждён! {PREMIUM_EMOJI['team_final_shield']}\n\n"
            f"{PREMIUM_EMOJI['team_final_star']} Теперь тебе доступен <b>Paradox Bot</b> "
            "<i>— сигнально-аналитический инструмент для поиска торговых ситуаций по FOREX и OTC-активам.</i>\n\n"
            "<blockquote><b><i>Что ты получаешь:</i></b>\n\n"
            "<i>• полный доступ к Paradox Bot;</i>\n"
            "<i>• алгоритмические прогнозы на основе более чем 30 индикаторов;</i>\n"
            "<i>• торговую пару и направление;</i>\n"
            "<i>• время экспирации и параметры входа;</i>\n"
            "<i>• сигналы и результаты закрытых сделок;</i>\n"
            "<i>• рабочие торговые сессии;</i>\n"
            "<i>• материалы и обновления команды;</i>\n"
            "<i>• доступ в закрытую VIP-группу.</i></blockquote>\n\n"
            f"{PREMIUM_EMOJI['team_final_one']} Нажми кнопку ниже и запусти <b>Paradox Bot</b>.\n\n"
            f"{PREMIUM_EMOJI['team_final_two']} Присоединяйся к закрытой группе команды, чтобы получать сигналы, "
            "следить за торговыми сессиями и видеть результаты закрытых сделок.\n\n"
            f"{PREMIUM_EMOJI['team_final_chat']} <b>ВСТУПИТЬ В VIP-ГРУППУ</b>\n\n"
            f"{PREMIUM_EMOJI['team_final_plus']} Доступ уже активирован. <b>Удачи и прибыльных сделок!</b> "
            f"{PREMIUM_EMOJI['team_final_crown']}{PREMIUM_EMOJI['team_final_candle']}"
        ),
        "en": (
            f"{PREMIUM_EMOJI['team_final_top']}{PREMIUM_EMOJI['team_final_top']} "
            f"<b>PARADOX TEAM ACCESS IS OPEN</b> "
            f"{PREMIUM_EMOJI['team_final_top']}{PREMIUM_EMOJI['team_final_top']}\n\n"
            f"All conditions are complete and your account is confirmed! {PREMIUM_EMOJI['team_final_shield']}\n\n"
            f"{PREMIUM_EMOJI['team_final_star']} You now have access to <b>Paradox Bot</b>, "
            "<i>a signal and analytics tool for FOREX and OTC market situations.</i>\n\n"
            "<blockquote><b><i>What you get:</i></b>\n\n"
            "<i>• full access to Paradox Bot;</i>\n"
            "<i>• algorithmic forecasts based on 30+ indicators;</i>\n"
            "<i>• trading pair and direction;</i>\n"
            "<i>• expiration time and entry parameters;</i>\n"
            "<i>• signals and closed trade results;</i>\n"
            "<i>• working trading sessions;</i>\n"
            "<i>• team materials and updates;</i>\n"
            "<i>• access to the closed VIP group.</i></blockquote>\n\n"
            f"{PREMIUM_EMOJI['team_final_one']} Tap the button below and launch <b>Paradox Bot</b>.\n\n"
            f"{PREMIUM_EMOJI['team_final_two']} Join the closed team group to receive signals, follow trading sessions, "
            "and see closed trade results.\n\n"
            f"{PREMIUM_EMOJI['team_final_chat']} <b>JOIN THE VIP GROUP</b>\n\n"
            f"{PREMIUM_EMOJI['team_final_plus']} Access is already active. <b>Good luck and profitable trades!</b> "
            f"{PREMIUM_EMOJI['team_final_crown']}{PREMIUM_EMOJI['team_final_candle']}"
        ),
    },
    "REMINDER-03": {
        "ru": (
            f"<b>Привет, бро</b>! У нас осталось 3 бесплатных места в команду, "
            f"забирай последнее! {PREMIUM_EMOJI['reminder_03_search']}\n\n"
            f"{PREMIUM_EMOJI['reminder_03_link']} <b><i>Статистика за закрытой VIP-группы за неделю:</i></b>\n\n"
            "<i>Общий доход трейдеров составил {team_total_income}$, личный доход трейдера Paradox FX "
            "составил {paradox_income}$</i>\n\n"
            f"{PREMIUM_EMOJI['reminder_03_hundred']} "
            f'<a href="{settings.team_vip_url or "https://t.me"}"><b>ПОСМОТРЕТЬ</b></a> '
            "<b>десятки реальных отзывов про работу с Paradox FX</b>\n\n"
            "Давай продолжим регистрацию и ты получишь бесплатный "
            f"<b>доступ за 1 минуту</b> {PREMIUM_EMOJI['reminder_03_heart']}\n\n"
            f"<b>{PREMIUM_EMOJI['reminder_03_down']}Нажми на кнопку \"Хочу в команду\""
            f"{PREMIUM_EMOJI['reminder_03_down']}</b>"
        ),
        "en": (
            f"<b>Hi, bro</b>! We have 3 free team spots left, take the last one! "
            f"{PREMIUM_EMOJI['reminder_03_search']}\n\n"
            f"{PREMIUM_EMOJI['reminder_03_link']} <b><i>Closed VIP group stats for the week:</i></b>\n\n"
            "<i>Total trader income was {team_total_income}$, and the personal income of the Paradox FX trader "
            "was {paradox_income}$</i>\n\n"
            f"{PREMIUM_EMOJI['reminder_03_hundred']} "
            f'<a href="{settings.team_vip_url or "https://t.me"}"><b>SEE</b></a> '
            "<b>dozens of real reviews about Paradox FX</b>\n\n"
            "Continue registration and get free "
            f"<b>access in 1 minute</b> {PREMIUM_EMOJI['reminder_03_heart']}\n\n"
            f"<b>{PREMIUM_EMOJI['reminder_03_down']}Tap \"I want to join the team\""
            f"{PREMIUM_EMOJI['reminder_03_down']}</b>"
        ),
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
SIGNAL_REQUEST_RE = re.compile(
    r"^\s*(?:(?:/signal|signal|сигнал)\s+)?([a-z]{3}/?[a-z]{3}(?:\s+otc)?|[a-z]{6}(?:\s+otc)?)\s+(\d{1,2})\s*(?:m|min|мин|м)?\s*$",
    re.IGNORECASE,
)
BOT_TEXTS = {
    "ru": {
        "start": LEGACY_START_TEXTS["ru"]["message"],
        "mini_app": LEGACY_START_TEXTS["ru"]["mini_app"],
        "text_format": LEGACY_START_TEXTS["ru"]["text_format"],
        "text_selected": "Текстовый формат выбран",
        "text_selected_message": (
            "Текстовый формат выбран.\n\n"
            "Сигналы будут приходить сообщениями Telegram. На первом этапе реальные сигналы еще не подключены."
        ),
        "open_mini_app": "⚡ Открыть Mini App",
        "team_start": "Вы выбрали маршрут команды.\n\nНажмите кнопку ниже, чтобы войти в команду Paradox FX.",
        "join_team": "ВОЙТИ В КОМАНДУ",
    },
    "en": {
        "start": LEGACY_START_TEXTS["en"]["message"],
        "mini_app": LEGACY_START_TEXTS["en"]["mini_app"],
        "text_format": LEGACY_START_TEXTS["en"]["text_format"],
        "text_selected": "Text format selected",
        "text_selected_message": (
            "Text format selected.\n\n"
            "Signals will be delivered as Telegram messages. Real signals are not connected at this stage."
        ),
        "open_mini_app": "⚡ Open Mini App",
        "team_start": "You selected the team route.\n\nTap the button below to join the Paradox FX team.",
        "join_team": "JOIN THE TEAM",
    },
    "es": {
        "start": "¡Hola! 👋\n\nSeñales profesionales para opciones binarias y forex.\n\nElige el formato de trabajo:",
        "mini_app": "⚡ Mini App (recomendado)",
        "text_format": "💬 Formato de texto",
        "text_selected": "Formato de texto seleccionado",
        "text_selected_message": (
            "Formato de texto seleccionado.\n\n"
            "Las señales llegarán como mensajes de Telegram. Las señales reales aún no están conectadas."
        ),
        "open_mini_app": "⚡ Abrir Mini App",
        "team_start": "Has elegido la ruta del equipo.\n\nPulsa el botón de abajo para unirte al equipo Paradox FX.",
        "join_team": "UNIRSE AL EQUIPO",
    },
    "pt": {
        "start": "Olá! 👋\n\nSinais profissionais para opções binárias e forex.\n\nEscolha o formato de trabalho:",
        "mini_app": "⚡ Mini App (recomendado)",
        "text_format": "💬 Formato de texto",
        "text_selected": "Formato de texto selecionado",
        "text_selected_message": (
            "Formato de texto selecionado.\n\n"
            "Os sinais chegarão como mensagens do Telegram. Sinais reais ainda não estão conectados."
        ),
        "open_mini_app": "⚡ Abrir Mini App",
        "team_start": "Você escolheu a rota da equipe.\n\nToque no botão abaixo para entrar na equipe Paradox FX.",
        "join_team": "ENTRAR NA EQUIPE",
    },
    "tr": {
        "start": "Merhaba! 👋\n\nBinary opsiyonlar ve forex piyasası için profesyonel işlem sinyalleri.\n\nÇalışma formatını seçin:",
        "mini_app": "⚡ Mini App (önerilir)",
        "text_format": "💬 Metin formatı",
        "text_selected": "Metin formatı seçildi",
        "text_selected_message": (
            "Metin formatı seçildi.\n\n"
            "Sinyaller Telegram mesajları olarak gelecek. Gerçek sinyaller bu aşamada bağlı değil."
        ),
        "open_mini_app": "⚡ Mini App'i aç",
        "team_start": "Takım rotasını seçtiniz.\n\nParadox FX ekibine katılmak için aşağıdaki düğmeye dokunun.",
        "join_team": "TAKIMA KATIL",
    },
    "ar": {
        "start": "مرحباً! 👋\n\nإشارات تداول احترافية للخيارات الثنائية وسوق الفوركس.\n\nاختر طريقة العمل:",
        "mini_app": "⚡ Mini App (موصى به)",
        "text_format": "💬 تنسيق نصي",
        "text_selected": "تم اختيار التنسيق النصي",
        "text_selected_message": (
            "تم اختيار التنسيق النصي.\n\n"
            "ستصل الإشارات كرسائل Telegram. الإشارات الحقيقية غير متصلة في هذه المرحلة."
        ),
        "open_mini_app": "⚡ فتح Mini App",
        "team_start": "لقد اخترت مسار الفريق.\n\nاضغط الزر أدناه للانضمام إلى فريق Paradox FX.",
        "join_team": "انضم إلى الفريق",
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

def funnel_texts(language: str) -> dict[str, str]:
    return FUNNEL_BUTTON_TEXTS.get(normalize_funnel_language(language), FUNNEL_BUTTON_TEXTS["en"])

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
        return {"inline_keyboard": [[{"text": texts["continue_registration"], "callback_data": "funnel:continue_topup_not_found"}]]}

    return None


def reminder_03_keyboard(language: str, target_node_code: str) -> dict[str, Any]:
    texts = funnel_texts(language)
    callback_action = "continue_topup_low" if target_node_code == "TOPUP-LOW" else "continue_topup_not_found"
    return {"inline_keyboard": [[{"text": texts["continue_registration"], "callback_data": f"funnel:{callback_action}"}]]}


def bot_reminder_keyboard(language: str, funnel_route: str = "BOT") -> dict[str, Any]:
    texts = funnel_texts(language)
    if funnel_route == "TEAM":
        return {"inline_keyboard": [[{"text": texts["join_team_start"], "callback_data": "funnel:team_start"}]]}

    return {"inline_keyboard": [[{"text": texts["get_bot"], "callback_data": "funnel:bot_start"}]]}

