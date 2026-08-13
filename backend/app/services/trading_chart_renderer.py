from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class TradeChartData:
    symbol: str
    market_type: str
    direction: str
    entry_time: datetime
    close_time: datetime
    expiry_seconds: int
    entry_price: float
    close_price: float
    result: str
    trade_amount: float = 1000
    payout_percent: float = 80
    flag_1: str = ""
    flag_2: str = ""
    history_payload: dict[str, Any] | None = None


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "seguiemj.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _extract_history_prices(payload: dict[str, Any] | None) -> list[float]:
    if not isinstance(payload, dict):
        return []

    containers = [
        payload.get("history"),
        payload.get("prices"),
        payload.get("data"),
        payload.get("candles"),
        payload.get("quotes"),
    ]
    prices: list[float] = []
    for container in containers:
        if not isinstance(container, list):
            continue
        for item in container:
            value: Any = item
            if isinstance(item, dict):
                value = (
                    item.get("price")
                    or item.get("close")
                    or item.get("value")
                    or item.get("bid")
                    or item.get("ask")
                    or item.get("last")
                )
            try:
                prices.append(float(value))
            except (TypeError, ValueError):
                continue
        if prices:
            return prices

    return []


def _scaled_points(prices: list[float], x: int, y: int, width: int, height: int) -> list[tuple[int, int]]:
    if not prices:
        return []
    minimum = min(prices)
    maximum = max(prices)
    spread = maximum - minimum or max(abs(maximum) * 0.0001, 0.0001)
    if len(prices) == 1:
        return [(x + width // 2, y + height // 2)]

    points: list[tuple[int, int]] = []
    for index, price in enumerate(prices):
        px = x + round((index / (len(prices) - 1)) * width)
        py = y + height - round(((price - minimum) / spread) * height)
        points.append((px, py))
    return points


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _price(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def render_trade_result_chart(data: TradeChartData) -> Path:
    is_win = data.result == "WIN"
    is_buy = data.direction == "BUY"
    accent = (80, 210, 104) if is_win else (235, 55, 60)
    line_color = (83, 155, 225)
    bg = (41, 46, 72)
    panel = (28, 31, 52)
    text = (245, 246, 250)
    muted = (183, 190, 208)

    image = Image.new("RGB", (1200, 900), bg)
    draw = ImageDraw.Draw(image)

    title_font = _font(42, bold=True)
    body_font = _font(34)
    small_font = _font(28)
    tiny_font = _font(24)

    asset = " ".join(part for part in [data.flag_1, data.symbol, data.flag_2, data.market_type] if part)
    trade_amount = data.trade_amount
    win_profit = trade_amount * (data.payout_percent / 100)
    payout = trade_amount + win_profit if is_win else 0
    profit = win_profit if is_win else -trade_amount

    draw.text((48, 42), f"☆ {data.symbol} +{data.payout_percent:.0f}%", fill=muted, font=title_font)
    draw.text((1020, 42), data.close_time.strftime("%H:%M"), fill=text, font=title_font)
    draw.text((48, 112), f"{'↗' if is_buy else '↘'} {_money(trade_amount)}", fill=accent, font=body_font)
    draw.text((540, 112), _money(payout), fill=accent if is_win else muted, font=body_font, anchor="ma")
    draw.text((1050, 112), f"{profit:+,}$", fill=accent if is_win else (240, 90, 90), font=body_font, anchor="ra")

    draw.rectangle((0, 190, 1200, 330), fill=(50, 56, 86))
    draw.text((64, 225), f"Время открытия:\n{data.entry_time.strftime('%H:%M:%S')}.000", fill=text, font=small_font)
    expiry_label = f"M{max(1, data.expiry_seconds // 60)}" if data.expiry_seconds >= 60 else f"{data.expiry_seconds}s"
    draw.text((600, 250), expiry_label, fill=text, font=body_font, anchor="mm")
    draw.text((1136, 225), f"Время закрытия:\n{data.close_time.strftime('%H:%M:%S')}.000", fill=text, font=small_font, anchor="ra")

    chart_x, chart_y, chart_w, chart_h = 78, 380, 1044, 310
    draw.rounded_rectangle((chart_x, chart_y, chart_x + chart_w, chart_y + chart_h), radius=14, fill=panel)
    draw.text((600, chart_y + 26), f"Ваш прогноз: {'КУПИТЬ' if is_buy else 'ПРОДАТЬ'}", fill=accent, font=small_font, anchor="ma")
    draw.text((310, chart_y + 78), f"Выплата: {_money(payout)}", fill=accent if is_win else muted, font=small_font, anchor="ma")
    draw.text((760, chart_y + 78), f"Прибыль:{profit:+,}$", fill=accent if is_win else (240, 90, 90), font=small_font, anchor="ma")

    prices = _extract_history_prices(data.history_payload)
    if len(prices) < 2:
        prices = [data.entry_price, (data.entry_price + data.close_price) / 2, data.close_price]
    prices = prices[-80:]
    points = _scaled_points(prices, chart_x + 62, chart_y + 134, chart_w - 124, chart_h - 170)

    for i in range(1, 6):
        gx = chart_x + 62 + round(((chart_w - 124) / 5) * i)
        draw.line((gx, chart_y + 130, gx, chart_y + chart_h - 36), fill=(58, 64, 92), width=2)
    for i in range(1, 4):
        gy = chart_y + 130 + round(((chart_h - 170) / 4) * i)
        draw.line((chart_x + 62, gy, chart_x + chart_w - 62, gy), fill=(58, 64, 92), width=2)

    if len(points) >= 2:
        draw.line(points, fill=line_color, width=6, joint="curve")
    entry_y = points[0][1] if points else chart_y + chart_h - 80
    draw.line((chart_x + 62, entry_y, chart_x + chart_w - 62, entry_y), fill=accent, width=5)
    draw.ellipse((chart_x + 56, entry_y - 7, chart_x + 70, entry_y + 7), fill=accent)
    draw.rounded_rectangle((chart_x + 80, entry_y - 42, chart_x + 210, entry_y + 6), radius=9, fill=(76, 147, 86))
    draw.text((chart_x + 145, entry_y - 35), _money(trade_amount), fill=text, font=tiny_font, anchor="ma")
    draw.line((chart_x + chart_w - 62, chart_y + 130, chart_x + chart_w - 62, chart_y + chart_h - 36), fill=(85, 105, 132), width=3)

    draw.text((48, 735), f"Сделка: {uuid4()}", fill=text, font=small_font)
    draw.text((48, 800), f"Цена открытия:\n{_price(data.entry_price)}", fill=text, font=small_font)
    draw.text((560, 800), f"Цена закрытия:\n{_price(data.close_price)}", fill=text, font=small_font, anchor="ma")
    difference = data.close_price - data.entry_price
    points_diff = int(round(difference * 1000000))
    draw.text((1130, 800), f"Разница:\n({points_diff:+} Пункты)", fill=accent if is_win else (240, 90, 90), font=small_font, anchor="ra")

    output = Path(gettempdir()) / f"paradox_trade_result_{uuid4().hex}.png"
    image.save(output, format="PNG", optimize=True)
    return output
