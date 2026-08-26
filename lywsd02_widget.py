#!/usr/bin/env python3
import asyncio
import json
import os
import shutil
import signal
import struct
import threading
import time
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except ValueError:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

from gi.repository import GLib, Gtk, Pango, PangoCairo

from bleak import BleakClient, BleakScanner

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_THRESHOLD = 10
DEVICE_NAMES = ("LYWSD02", "MHO-C303")
UUID_TIME = "EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6"
UUID_DATA = "EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6"
UUID_BATT = "EBE0CCC4-7A0A-4B0C-8A1A-6FF2997DA3A6"
CONFIG_PATH = os.path.join(GLib.get_user_config_dir(), "lywsd02-widget", "config.json")
AUTOSTART_PATH = os.path.join(GLib.get_user_config_dir(), "autostart", "lywsd02-widget.desktop")

STRINGS = {
    "ru": {
        "time": "Время",
        "drift": "Расхождение",
        "temp": "Температура",
        "humi": "Влажность",
        "batt": "Батарея",
        "sec": "с",
        "updating": "Обновление…",
        "updated": "Обновлено в",
        "no_link": "Нет связи",
        "synced": "время синхронизировано",
        "refresh": "Обновить сейчас",
        "settings": "Настройки",
        "quit": "Выход",
        "lang": "Язык",
        "tz": "Часовой пояс",
        "tz_system": "Системный",
        "autostart": "Автозапуск при входе",
        "autosync": "Автосинхронизация времени",
        "sync_now": "Синхронизировать",
        "sync_requested": "Запрошено, результат появится в меню",
        "search": "Поиск",
        "mood": "Комфорт",
        "comfortable": "комфортно",
        "cold": "холодно",
        "hot": "жарко",
        "dry": "сухо",
        "humid": "влажно",
        "face_style": "Мордочка",
        "device": "Часы",
        "no_device": "не выбраны",
        "nodev_status": "Часы не выбраны",
        "scan_title": "Поиск часов",
        "scanning": "Идёт поиск…",
        "scan_none": "Ничего не найдено. Поднесите часы ближе и попробуйте ещё раз",
        "scan_found": "Найдено",
        "poll": "Опрос, мин",
        "tray_mode": "В трее",
        "tray_icon": "иконка",
        "tray_data": "данные",
        "tray_data_face": "данные + мордашка",
        "tray_face": "мордашка",
        "tray_temp": "температура",
        "tray_humi": "влажность",
    },
    "en": {
        "time": "Time",
        "drift": "Drift",
        "temp": "Temperature",
        "humi": "Humidity",
        "batt": "Battery",
        "sec": "s",
        "updating": "Refreshing…",
        "updated": "Updated at",
        "no_link": "No connection",
        "synced": "time synced",
        "refresh": "Refresh now",
        "settings": "Settings",
        "quit": "Quit",
        "lang": "Language",
        "tz": "Time zone",
        "tz_system": "System",
        "autostart": "Start at login",
        "autosync": "Auto time sync",
        "sync_now": "Sync",
        "sync_requested": "Requested, result will appear in the menu",
        "search": "Search",
        "mood": "Comfort",
        "comfortable": "comfortable",
        "cold": "cold",
        "hot": "hot",
        "dry": "dry",
        "humid": "humid",
        "face_style": "Face",
        "device": "Device",
        "no_device": "not selected",
        "nodev_status": "Device not selected",
        "scan_title": "Device search",
        "scanning": "Scanning…",
        "scan_none": "Nothing found. Bring the clock closer and try again",
        "scan_found": "Found",
        "poll": "Poll, min",
        "tray_mode": "Tray",
        "tray_icon": "icon",
        "tray_data": "data",
        "tray_data_face": "data + face",
        "tray_face": "face",
        "tray_temp": "temperature",
        "tray_humi": "humidity",
    },
}


def default_lang():
    return "ru" if os.environ.get("LANG", "").lower().startswith("ru") else "en"


DEFAULTS = {
    "lang": default_lang(),
    "tz": "system",
    "autosync": True,
    "face": "emoji",
    "tray": "icon",
    "comfort": {"t_lo": 19.0, "t_hi": 27.0, "h_lo": 20.0, "h_hi": 85.0},
}

FACES = {
    "happy": {"emoji": "🙂", "text": "(^_^)"},
    "sad": {"emoji": "🙁", "text": "(-‸-)"},
}

TRAY_MODES = ("icon", "data", "data_face", "face", "temp", "humi")

ICON_DIR = os.path.join(GLib.get_user_cache_dir(), "lywsd02-widget")


def measure_text(text):
    try:
        fontmap = PangoCairo.FontMap.get_default()
        context = fontmap.create_context()
        layout = Pango.Layout(context)
        desc = Pango.FontDescription("Ubuntu")
        desc.set_absolute_size(14 * Pango.SCALE)
        layout.set_font_description(desc)
        layout.set_text(text, -1)
        return layout.get_pixel_size().width
    except Exception:
        return int(len(text) * 8)


SEG_MAP = {
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgedc",
    "7": "abc",
    "8": "abcdefg",
    "9": "abfgcd",
    "-": "g",
}

INK = (25, 25, 23, 255)
BODY_WHITE = (255, 255, 255, 255)
FRAME_GRAY = (218, 222, 221, 255)
SCREEN_GRAY = (205, 210, 207, 255)


def draw_7seg(dr, x, y, w, h, ch, t):
    on = SEG_MAP.get(ch, "")
    seam = t * 0.12
    cut = t * 0.22
    jg = t * 0.11
    taper = t * 0.65
    ft = t * 0.16
    hh = h / 2
    vtop = y + hh - jg
    vbot = y + hh + jg
    vy0 = y + seam
    vy1 = y + h - seam
    if "a" in on:
        dr.polygon(
            [(x + cut, y), (x + w - cut, y), (x + w - t, y + t), (x + t, y + t)], fill=INK
        )
    if "d" in on:
        dr.polygon(
            [(x + t, y + h - t), (x + w - t, y + h - t), (x + w - cut, y + h), (x + cut, y + h)],
            fill=INK,
        )
    if "g" in on:
        gm = t * 0.4
        gt = t * 0.5
        gy = y + hh - t / 2
        gx = x + gm
        ln = w - 2 * gm
        dr.polygon(
            [
                (gx + gt, gy),
                (gx + ln - gt, gy),
                (gx + ln, gy + t / 2),
                (gx + ln - gt, gy + t),
                (gx + gt, gy + t),
                (gx, gy + t / 2),
            ],
            fill=INK,
        )
    if "f" in on:
        dr.polygon(
            [
                (x, vy0),
                (x + t, vy0 + t),
                (x + t, vtop - taper),
                (x + t / 2 + ft, vtop),
                (x + t / 2 - ft, vtop),
                (x, vtop - taper),
            ],
            fill=INK,
        )
    if "b" in on:
        dr.polygon(
            [
                (x + w, vy0),
                (x + w, vtop - taper),
                (x + w - t / 2 + ft, vtop),
                (x + w - t / 2 - ft, vtop),
                (x + w - t, vtop - taper),
                (x + w - t, vy0 + t),
            ],
            fill=INK,
        )
    if "e" in on:
        dr.polygon(
            [
                (x, vy1),
                (x, vbot + taper),
                (x + t / 2 - ft, vbot),
                (x + t / 2 + ft, vbot),
                (x + t, vbot + taper),
                (x + t, vy1 - t),
            ],
            fill=INK,
        )
    if "c" in on:
        dr.polygon(
            [
                (x + w, vy1),
                (x + w - t, vy1 - t),
                (x + w - t, vbot + taper),
                (x + w - t / 2 - ft, vbot),
                (x + w - t / 2 + ft, vbot),
                (x + w, vbot + taper),
            ],
            fill=INK,
        )


def draw_seg_number(dr, x, y, text, w, h, t, gap, colon_slot=None):
    for ch in text:
        if ch == ":":
            slot = colon_slot or (t * 3)
            x -= gap
            dt = t * 0.65
            cx = x + (slot - dt) * 0.5
            dr.rectangle([cx, y + h * 0.312, cx + dt, y + h * 0.312 + dt], fill=INK)
            dr.rectangle([cx, y + h * 0.628, cx + dt, y + h * 0.628 + dt], fill=INK)
            x += slot
        elif ch == ".":
            dr.rectangle([x, y + h - t, x + t, y + h], fill=INK)
            x += t + gap
        else:
            draw_7seg(dr, x, y, w, h, ch, t)
            x += w + gap
    return x


def draw_screen_face(dr, x, y, h, lw, happy):
    def ln(points):
        dr.line(points, fill=INK, width=int(lw), joint="curve")
        r = lw / 2 - 0.5
        for px, py in (points[0], points[-1]):
            dr.ellipse([px - r, py - r, px + r, py + r], fill=INK)

    w = h * 2.55
    pw = h * 0.75
    dr.arc([x, y - h * 0.1, x + pw, y + h * 1.1], 130, 230, fill=INK, width=int(lw))
    dr.arc([x + w - pw, y - h * 0.1, x + w, y + h * 1.1], 310, 50, fill=INK, width=int(lw))
    ew = w * 0.20
    eh = h * 0.26
    ey = y + h * 0.08
    e1 = x + w * 0.20
    e2 = x + w * 0.64
    my = y + h * 0.88
    m1 = x + w * 0.38
    m2 = x + w * 0.58
    if happy:
        ln([(e1, ey + eh), (e1 + ew / 2, ey), (e1 + ew, ey + eh)])
        ln([(e2, ey + eh), (e2 + ew / 2, ey), (e2 + ew, ey + eh)])
        dr.rounded_rectangle([m1, my - lw / 2, m2, my + lw / 2], radius=lw / 2, fill=INK)
    else:
        eyc = ey + eh * 0.6
        ln([(e1, eyc), (e1 + ew, eyc)])
        ln([(e2, eyc), (e2 + ew, eyc)])
        ln([(m1, my), ((m1 + m2) / 2, my - eh), (m2, my)])


def load_pil_font(size):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_clock_face(path, time_text, humi_text, temp_text, happy, out_w=440):
    s = 3
    W, H = 480 * s, 238 * s
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle([0, 0, W - 1, H - 1], radius=23 * s, fill=BODY_WHITE)
    dr.rounded_rectangle([10 * s, 10 * s, W - 10 * s, H - 10 * s], radius=17 * s, fill=FRAME_GRAY)
    dr.rounded_rectangle([48 * s, 48 * s, 432 * s, 189 * s], radius=4 * s, fill=SCREEN_GRAY)

    draw_seg_number(dr, 78 * s, 56 * s, time_text, 54 * s, 94 * s, 9 * s, 23 * s, colon_slot=48 * s)

    sw, sh, st, sg = 11.5 * s, 21 * s, 2.5 * s, 3 * s
    by = 161 * s
    x = draw_seg_number(dr, 180.5 * s, by, humi_text, sw, sh, st, sg)
    dr.text((x + 1 * s, by + 13 * s), "%", font=load_pil_font(int(9 * s)), fill=INK)

    x = draw_seg_number(dr, 262 * s, by, temp_text, sw, sh, st, sg)
    dr.ellipse(
        [x + 2.5 * s, by + 15.5 * s, x + 5.3 * s, by + 18.3 * s], outline=INK, width=int(1.1 * s)
    )
    dr.text((x + 6.5 * s, by + 14.5 * s), "C", font=load_pil_font(int(7 * s)), fill=INK)

    if happy is not None:
        draw_screen_face(dr, 333 * s, by, 21 * s, 2.5 * s, happy)

    img = img.resize((out_w, H * out_w // W), Image.LANCZOS)
    img.save(path)


CLOCK_GLYPH = (
    '<rect x="2.75" y="2.75" width="16.5" height="16.5" rx="3.5" fill="none" '
    'stroke="#e8e8e8" stroke-width="1.5"/>'
    '<g fill="#e8e8e8">'
    '<rect x="5.5" y="7" width="2.2" height="5" rx="0.6"/>'
    '<rect x="8.6" y="7" width="2.2" height="5" rx="0.6"/>'
    '<circle cx="12.3" cy="8.2" r="0.85"/>'
    '<circle cx="12.3" cy="10.8" r="0.85"/>'
    '<rect x="13.7" y="7" width="2.2" height="5" rx="0.6"/>'
    '<rect x="5.5" y="14" width="4.5" height="1.6" rx="0.8"/>'
    '<rect x="11.5" y="14" width="4.5" height="1.6" rx="0.8"/>'
    "</g>"
)


def build_tray_svg(text, face_kind, clock=False):
    height = 17
    if clock:
        inner = 16
    else:
        text_w = measure_text(text) if text else 0
        gap = 4 if text and face_kind else 0
        face_w = 16 if face_kind else 0
        inner = max(text_w + gap + face_w, 1)
    width = max(inner, 26)
    off = (width - inner) / 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<g transform="translate({off:.1f},0)">',
    ]
    if clock:
        parts.append(f'<g transform="translate(0,0.5) scale({16 / 22:.4f})">{CLOCK_GLYPH}</g>')
    else:
        if text:
            parts.append(
                '<text x="0" y="12.5" font-family="Ubuntu, Cantarell, DejaVu Sans, sans-serif" '
                f'font-size="14" fill="#f2f2f2">{escape(text)}</text>'
            )
        if face_kind:
            x = text_w + gap
            mouth = (
                "M4.5 9.3 Q8 12.8 11.5 9.3" if face_kind == "happy" else "M4.5 12 Q8 8.6 11.5 12"
            )
            parts.append(
                f'<g transform="translate({x},0.5)">'
                '<circle cx="8" cy="8" r="7.5" fill="#fcc21b"/>'
                '<circle cx="5.2" cy="6.2" r="1.2" fill="#46342a"/>'
                '<circle cx="10.8" cy="6.2" r="1.2" fill="#46342a"/>'
                f'<path d="{mouth}" stroke="#46342a" stroke-width="1.4" fill="none" '
                'stroke-linecap="round"/>'
                "</g>"
            )
    parts.append("</g></svg>")
    return "".join(parts)


def face_glyph(happy):
    style = "text" if config.get("face") == "text" else "emoji"
    return FACES["happy" if happy else "sad"][style]


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


config = load_config()


def save_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def L(key):
    lang = config.get("lang", "ru")
    return STRINGS.get(lang, STRINGS["ru"]).get(key, key)


TZ_OFFSETS = sorted(
    set(range(-720, 841, 60))
    | {-570, -210, -150, 210, 270, 330, 345, 390, 525, 570, 630, 765, 825}
)


def offset_label(minutes):
    sign = "+" if minutes >= 0 else "-"
    m = abs(minutes)
    return f"UTC{sign}{m // 60:02d}:{m % 60:02d}"


TZ_CITIES = {
    "ru": {
        -720: "о-ва Бейкер и Хауленд",
        -660: "Паго-Паго, Ниуэ",
        -600: "Гонолулу",
        -570: "Маркизские о-ва",
        -540: "Анкоридж",
        -480: "Лос-Анджелес, Ванкувер",
        -420: "Денвер, Финикс",
        -360: "Чикаго, Мехико",
        -300: "Нью-Йорк, Торонто, Лима",
        -240: "Сантьяго, Каракас",
        -210: "Сент-Джонс",
        -180: "Сан-Паулу, Буэнос-Айрес",
        -150: "Ньюфаундленд (лето)",
        -120: "Южная Георгия",
        -60: "Азорские о-ва, Кабо-Верде",
        0: "Лондон, Лиссабон, Аккра",
        60: "Берлин, Париж, Мадрид",
        120: "Афины, Каир, Йоханнесбург",
        180: "Москва, Стамбул, Эр-Рияд",
        210: "Тегеран",
        240: "Дубай, Баку, Тбилиси",
        270: "Кабул",
        300: "Екатеринбург, Ташкент, Карачи",
        330: "Дели, Мумбаи, Коломбо",
        345: "Катманду",
        360: "Алматы, Дакка, Омск",
        390: "Янгон",
        420: "Бангкок, Джакарта, Новосибирск",
        480: "Пекин, Сингапур, Иркутск",
        525: "Юкла",
        540: "Токио, Сеул, Якутск",
        570: "Аделаида, Дарвин",
        600: "Сидней, Владивосток",
        630: "о. Лорд-Хау",
        660: "Магадан, Нумеа",
        720: "Окленд, Камчатка, Фиджи",
        765: "о-ва Чатем",
        780: "Нукуалофа, Апиа",
        825: "о-ва Чатем (лето)",
        840: "Киритимати",
    },
    "en": {
        -720: "Baker & Howland Is.",
        -660: "Pago Pago, Niue",
        -600: "Honolulu",
        -570: "Marquesas Is.",
        -540: "Anchorage",
        -480: "Los Angeles, Vancouver",
        -420: "Denver, Phoenix",
        -360: "Chicago, Mexico City",
        -300: "New York, Toronto, Lima",
        -240: "Santiago, Caracas",
        -210: "St. John's",
        -180: "São Paulo, Buenos Aires",
        -150: "Newfoundland (DST)",
        -120: "South Georgia",
        -60: "Azores, Cape Verde",
        0: "London, Lisbon, Accra",
        60: "Berlin, Paris, Madrid",
        120: "Athens, Cairo, Johannesburg",
        180: "Moscow, Istanbul, Riyadh",
        210: "Tehran",
        240: "Dubai, Baku, Tbilisi",
        270: "Kabul",
        300: "Yekaterinburg, Tashkent, Karachi",
        330: "Delhi, Mumbai, Colombo",
        345: "Kathmandu",
        360: "Almaty, Dhaka, Omsk",
        390: "Yangon",
        420: "Bangkok, Jakarta, Novosibirsk",
        480: "Beijing, Singapore, Irkutsk",
        525: "Eucla",
        540: "Tokyo, Seoul, Yakutsk",
        570: "Adelaide, Darwin",
        600: "Sydney, Vladivostok",
        630: "Lord Howe Is.",
        660: "Magadan, Noumea",
        720: "Auckland, Kamchatka, Fiji",
        765: "Chatham Is.",
        780: "Nuku'alofa, Apia",
        825: "Chatham Is. (DST)",
        840: "Kiritimati",
    },
}


def tz_entry_label(minutes):
    lang = config.get("lang", "ru")
    cities = TZ_CITIES.get(lang, TZ_CITIES["en"]).get(minutes)
    label = f"({offset_label(minutes)})"
    return f"{label} {cities}" if cities else label


def system_tz_minutes():
    offset = datetime.now().astimezone().utcoffset() or timedelta()
    return round(offset.total_seconds() / 60)


def tz_config_minutes(value):
    value = float(value)
    if abs(value) <= 14:
        value *= 60
    return round(value)


def desired_tz_minutes():
    value = config.get("tz", "system")
    return system_tz_minutes() if value == "system" else tz_config_minutes(value)


def device_mac():
    return (config.get("mac") or os.environ.get("LYWSD02_MAC") or "").strip()


def poll_seconds():
    try:
        value = int(config.get("poll") or os.environ.get("LYWSD02_POLL") or 600)
    except (TypeError, ValueError):
        value = 600
    return max(60, value)


def comfort_range():
    c = config.get("comfort") or {}
    d = DEFAULTS["comfort"]
    return (
        float(c.get("t_lo", d["t_lo"])),
        float(c.get("t_hi", d["t_hi"])),
        float(c.get("h_lo", d["h_lo"])),
        float(c.get("h_hi", d["h_hi"])),
    )


def autostart_enabled():
    return os.path.exists(AUTOSTART_PATH)


def set_autostart(enabled):
    if enabled:
        os.makedirs(os.path.dirname(AUTOSTART_PATH), exist_ok=True)
        for src in (
            os.path.join(GLib.get_user_data_dir(), "applications", "lywsd02-widget.desktop"),
            "/usr/share/applications/lywsd02-widget.desktop",
        ):
            if os.path.exists(src):
                shutil.copy(src, AUTOSTART_PATH)
                return
        with open(os.path.join(APP_DIR, "lywsd02-widget.desktop.in")) as f:
            body = (
                f.read()
                .replace("@EXEC@", os.path.join(APP_DIR, "run.sh"))
                .replace("@ICON@", os.path.join(APP_DIR, "lywsd02-widget.svg"))
            )
        with open(AUTOSTART_PATH, "w") as f:
            f.write(body)
    else:
        try:
            os.remove(AUTOSTART_PATH)
        except FileNotFoundError:
            pass


async def poll_device(mac, sync_requested):
    got = asyncio.Event()
    result = {}

    def on_notify(_, data):
        if len(data) >= 3:
            result["temp"] = struct.unpack_from("<h", data, 0)[0] / 100.0
            result["humi"] = data[2]
            got.set()

    desired = desired_tz_minutes()
    async with BleakClient(mac, timeout=25.0) as client:
        raw = await client.read_gatt_char(UUID_TIME)
        epoch = struct.unpack_from("<I", raw, 0)[0]
        tz = struct.unpack_from("<b", raw, 4)[0] if len(raw) >= 5 else 0
        now = int(datetime.now(tz=timezone.utc).timestamp())
        drift = epoch + tz * 3600 - now - desired * 60
        need = sync_requested or (config.get("autosync") and abs(drift) > SYNC_THRESHOLD)
        if need:
            byte = desired // 60
            now = int(datetime.now(tz=timezone.utc).timestamp())
            epoch_w = now + (desired - byte * 60) * 60
            await client.write_gatt_char(UUID_TIME, struct.pack("<Ib", epoch_w, byte), response=True)
            epoch, tz, drift = epoch_w, byte, 0
            result["synced"] = True
        result["epoch"] = epoch
        result["tz"] = tz
        result["drift"] = drift
        try:
            result["batt"] = (await client.read_gatt_char(UUID_BATT))[0]
        except Exception:
            result["batt"] = None
        await client.start_notify(UUID_DATA, on_notify)
        try:
            await asyncio.wait_for(got.wait(), timeout=20.0)
        except asyncio.TimeoutError:
            pass
        await client.stop_notify(UUID_DATA)
    return result


class SettingsWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(title=L("settings"))
        self.app = app
        self.set_resizable(False)
        self.set_border_width(12)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(box)
        self.clock_path = os.path.join(ICON_DIR, "clockface.png")
        self.clock_image = Gtk.Image()
        box.pack_start(self.clock_image, False, False, 0)
        self.update_clock()
        self._clock_timer = GLib.timeout_add_seconds(1, self.update_clock)
        self.connect("destroy", self.on_window_destroy)
        grid = Gtk.Grid(row_spacing=8, column_spacing=12)
        box.pack_start(grid, True, True, 0)

        lang_combo = Gtk.ComboBoxText()
        lang_combo.append("ru", "Русский")
        lang_combo.append("en", "English")
        lang_combo.set_active_id(config.get("lang", "ru"))
        lang_combo.connect("changed", self.on_lang)
        grid.attach(Gtk.Label(label=L("lang"), xalign=0), 0, 0, 1, 1)
        grid.attach(lang_combo, 1, 0, 1, 1)

        self.tz_button = Gtk.Button(label=self.tz_button_label())
        self.tz_button.connect("clicked", self.open_tz_dialog)
        grid.attach(Gtk.Label(label=L("tz"), xalign=0), 0, 1, 1, 1)
        grid.attach(self.tz_button, 1, 1, 1, 1)

        face_combo = Gtk.ComboBoxText()
        face_combo.append("emoji", FACES["happy"]["emoji"])
        face_combo.append("text", FACES["happy"]["text"])
        face_combo.set_active_id("text" if config.get("face") == "text" else "emoji")
        face_combo.connect("changed", self.on_face)
        grid.attach(Gtk.Label(label=L("face_style"), xalign=0), 0, 2, 1, 1)
        grid.attach(face_combo, 1, 2, 1, 1)

        tray_combo = Gtk.ComboBoxText()
        for mode_id in TRAY_MODES:
            tray_combo.append(mode_id, L(f"tray_{mode_id}"))
        active_tray = config.get("tray")
        tray_combo.set_active_id(active_tray if active_tray in TRAY_MODES else "icon")
        tray_combo.connect("changed", self.on_tray)
        grid.attach(Gtk.Label(label=L("tray_mode"), xalign=0), 0, 3, 1, 1)
        grid.attach(tray_combo, 1, 3, 1, 1)

        self.device_button = Gtk.Button(label=device_mac() or L("no_device"))
        self.device_button.connect("clicked", self.open_device_dialog)
        grid.attach(Gtk.Label(label=L("device"), xalign=0), 0, 4, 1, 1)
        grid.attach(self.device_button, 1, 4, 1, 1)

        poll_spin = Gtk.SpinButton.new_with_range(1, 120, 1)
        poll_spin.set_value(poll_seconds() // 60)
        poll_spin.connect("value-changed", self.on_poll)
        grid.attach(Gtk.Label(label=L("poll"), xalign=0), 0, 5, 1, 1)
        grid.attach(poll_spin, 1, 5, 1, 1)

        for combo in (lang_combo, face_combo, tray_combo):
            for cell in combo.get_cells():
                cell.set_property("xalign", 0)
        css = Gtk.CssProvider()
        css.load_from_data(b"button { padding-left: 8px; }")
        for btn in (self.tz_button, self.device_button):
            child = btn.get_child()
            if child:
                child.set_halign(Gtk.Align.START)
            btn.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        autostart_check = Gtk.CheckButton(label=L("autostart"))
        autostart_check.set_active(autostart_enabled())
        autostart_check.connect("toggled", self.on_autostart)
        grid.attach(autostart_check, 1, 6, 1, 1)

        autosync_check = Gtk.CheckButton(label=L("autosync"))
        autosync_check.set_active(bool(config.get("autosync")))
        autosync_check.connect("toggled", self.on_autosync)
        grid.attach(autosync_check, 1, 7, 1, 1)

        sync_btn = Gtk.Button(label=L("sync_now"))
        sync_btn.connect("clicked", self.on_sync)
        grid.attach(sync_btn, 0, 8, 2, 1)

        self.note = Gtk.Label(label="", xalign=0)
        self.note.get_style_context().add_class("dim-label")
        grid.attach(self.note, 0, 9, 2, 1)

    def on_lang(self, combo):
        lid = combo.get_active_id()
        if lid and lid != config.get("lang"):
            config["lang"] = lid
            save_config()
            self.app.retranslate()
            self.destroy()
            self.app.on_settings(None)

    def update_clock(self):
        try:
            d = self.app.last_data
            if d and "temp" in d:
                watch = datetime.fromtimestamp(
                    self.app.watch_epoch(), timezone(timedelta(hours=d["tz"]))
                )
                render_clock_face(
                    self.clock_path,
                    watch.strftime("%H:%M"),
                    str(d["humi"]),
                    f"{d['temp']:.1f}",
                    self.app.comfort_ok,
                    out_w=220,
                )
            else:
                render_clock_face(self.clock_path, "--:--", "--", "--.-", None, out_w=220)
            self.clock_image.set_from_file(self.clock_path)
        except Exception:
            pass
        return True

    def on_window_destroy(self, *_):
        if self._clock_timer:
            GLib.source_remove(self._clock_timer)
            self._clock_timer = None

    def tz_button_label(self):
        value = config.get("tz", "system")
        if value == "system":
            return f"{L('tz_system')} ({offset_label(system_tz_minutes())})"
        return tz_entry_label(tz_config_minutes(value))

    def open_tz_dialog(self, _):
        dialog = Gtk.Dialog(title=L("tz"), transient_for=self, modal=True)
        dialog.set_default_size(400, 460)
        box = dialog.get_content_area()
        box.set_spacing(6)
        box.set_border_width(6)
        search = Gtk.SearchEntry()
        search.set_placeholder_text(L("search"))
        box.pack_start(search, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        listbox = Gtk.ListBox()
        listbox.set_activate_on_single_click(True)
        active = config.get("tz", "system")
        active_value = active if active == "system" else tz_config_minutes(active)
        entries = [("system", f"{L('tz_system')} ({offset_label(system_tz_minutes())})")]
        entries += [(m, tz_entry_label(m)) for m in TZ_OFFSETS]
        selected = None
        for value, text in entries:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=text, xalign=0)
            label.set_margin_start(8)
            label.set_margin_end(8)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            row.add(label)
            row.tz_value = value
            listbox.add(row)
            if value == active_value:
                selected = row
        if selected:
            listbox.select_row(selected)
        listbox.set_filter_func(
            lambda row: search.get_text().lower() in row.get_child().get_text().lower()
        )
        search.connect("search-changed", lambda _: listbox.invalidate_filter())
        listbox.connect("row-activated", self.on_tz_row, dialog)
        scroll.add(listbox)
        box.pack_start(scroll, True, True, 0)
        dialog.show_all()
        search.grab_focus()
        if selected:
            GLib.idle_add(selected.grab_focus)
            GLib.idle_add(search.grab_focus)

    def on_tz_row(self, _, row, dialog):
        value = row.tz_value
        if value != config.get("tz"):
            config["tz"] = value
            save_config()
            self.app.request_sync()
            self.note.set_label(L("sync_requested"))
        self.tz_button.set_label(self.tz_button_label())
        dialog.destroy()

    def open_device_dialog(self, _):
        dialog = Gtk.Dialog(title=L("scan_title"), transient_for=self, modal=True)
        dialog.set_default_size(420, 380)
        box = dialog.get_content_area()
        box.set_spacing(6)
        box.set_border_width(6)
        status = Gtk.Label(label=L("scanning"), xalign=0)
        box.pack_start(status, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        listbox = Gtk.ListBox()
        listbox.set_activate_on_single_click(True)
        listbox.connect("row-activated", self.on_device_row, dialog)
        scroll.add(listbox)
        box.pack_start(scroll, True, True, 0)
        dialog.show_all()
        stop = threading.Event()
        dialog.connect("destroy", lambda *_: stop.set())
        threading.Thread(
            target=self.scan_worker, args=(listbox, status, stop), daemon=True
        ).start()

    def scan_worker(self, listbox, status, stop):
        found = {}

        def on_adv(device, adv):
            name = adv.local_name or device.name or ""
            if not any(n in name for n in DEVICE_NAMES):
                return
            if device.address in found or stop.is_set():
                return
            found[device.address] = name
            GLib.idle_add(self.add_device_row, listbox, device.address, name, adv.rssi, stop)

        async def run():
            scanner = BleakScanner(detection_callback=on_adv)
            await scanner.start()
            for _ in range(24):
                if stop.is_set():
                    break
                await asyncio.sleep(0.5)
            await scanner.stop()

        try:
            asyncio.run(run())
        except Exception as exc:
            if not stop.is_set():
                GLib.idle_add(status.set_label, str(exc)[:120])
            return
        if not stop.is_set():
            text = f"{L('scan_found')}: {len(found)}" if found else L("scan_none")
            GLib.idle_add(status.set_label, text)

    def add_device_row(self, listbox, mac, name, rssi, stop):
        if stop.is_set():
            return False
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=f"{name}   {mac}   {rssi} dBm", xalign=0)
        label.set_margin_start(8)
        label.set_margin_end(8)
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        row.add(label)
        row.mac = mac
        listbox.add(row)
        row.show_all()
        return False

    def on_device_row(self, _, row, dialog):
        config["mac"] = row.mac
        save_config()
        self.device_button.set_label(row.mac)
        self.app.on_refresh(None)
        dialog.destroy()

    def on_poll(self, spin):
        config["poll"] = spin.get_value_as_int() * 60
        save_config()

    def on_face(self, combo):
        config["face"] = combo.get_active_id()
        save_config()
        self.app.render()

    def on_tray(self, combo):
        config["tray"] = combo.get_active_id()
        save_config()
        self.app.render()

    def on_autostart(self, check):
        set_autostart(check.get_active())

    def on_autosync(self, check):
        config["autosync"] = check.get_active()
        save_config()

    def on_sync(self, _):
        self.app.request_sync()
        self.note.set_label(L("sync_requested"))


class Widget:
    def __init__(self):
        os.makedirs(ICON_DIR, exist_ok=True)
        shutil.copy(os.path.join(APP_DIR, "lywsd02-widget.svg"), ICON_DIR)
        self._icon_seq = 1
        with open(os.path.join(ICON_DIR, "lywsd02-label-1.svg"), "w") as f:
            f.write(build_tray_svg("", None, clock=True))
        self.indicator = AppIndicator.Indicator.new(
            "lywsd02-widget",
            "lywsd02-label-1",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_icon_theme_path(ICON_DIR)
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("LYWSD02")

        self.last_data = None
        self.last_status = ("updating",)
        self.comfort_ok = True
        self.settings = None

        self.menu = Gtk.Menu()
        self.rows = {}
        for key in ("time", "drift", "temp", "humi", "mood", "batt"):
            item = Gtk.MenuItem(label="")
            item.set_sensitive(False)
            self.menu.append(item)
            self.rows[key] = item

        self.menu.append(Gtk.SeparatorMenuItem())
        self.status_row = Gtk.MenuItem(label="")
        self.status_row.set_sensitive(False)
        self.menu.append(self.status_row)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.refresh_item = Gtk.MenuItem(label="")
        self.refresh_item.connect("activate", self.on_refresh)
        self.menu.append(self.refresh_item)
        self.settings_item = Gtk.MenuItem(label="")
        self.settings_item.connect("activate", self.on_settings)
        self.menu.append(self.settings_item)
        self.quit_item = Gtk.MenuItem(label="")
        self.quit_item.connect("activate", self.on_quit)
        self.menu.append(self.quit_item)

        self.retranslate()
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        self.indicator.set_secondary_activate_target(self.settings_item)

        self.wake = threading.Event()
        self.sync_flag = False
        self.stop = False
        self.worker = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker.start()
        GLib.timeout_add_seconds(1, self.on_tick)

    def on_tick(self):
        d = self.last_data
        if d:
            try:
                watch = datetime.fromtimestamp(
                    self.watch_epoch(), timezone(timedelta(hours=d["tz"]))
                )
                self.rows["time"].set_label(f"{L('time')}: {watch.strftime('%H:%M:%S')}")
            except Exception:
                pass
        return True

    def worker_loop(self):
        while not self.stop:
            sync = self.sync_flag
            self.sync_flag = False
            mac = device_mac()
            if mac:
                try:
                    data = asyncio.run(poll_device(mac, sync))
                    GLib.idle_add(self.apply_data, data)
                except Exception as exc:
                    GLib.idle_add(self.apply_error, str(exc))
            else:
                GLib.idle_add(self.apply_no_device)
            self.wake.wait(poll_seconds())
            self.wake.clear()

    def watch_epoch(self):
        d = self.last_data
        epoch = d["epoch"]
        if "at" in d:
            epoch += int(time.monotonic() - d["at"])
        return epoch

    def render(self):
        d = self.last_data
        if d:
            tzinfo = timezone(timedelta(hours=d["tz"]))
            watch = datetime.fromtimestamp(self.watch_epoch(), tzinfo)
            self.rows["time"].set_label(f"{L('time')}: {watch.strftime('%H:%M:%S')}")
            self.rows["drift"].set_label(f"{L('drift')}: {d['drift']:+d} {L('sec')}")
            if "temp" in d:
                self.rows["temp"].set_label(f"{L('temp')}: {d['temp']:.1f} °C")
                self.rows["humi"].set_label(f"{L('humi')}: {d['humi']}%")
                t_lo, t_hi, h_lo, h_hi = comfort_range()
                problems = []
                if d["temp"] < t_lo:
                    problems.append(L("cold"))
                if d["temp"] > t_hi:
                    problems.append(L("hot"))
                if d["humi"] < h_lo:
                    problems.append(L("dry"))
                if d["humi"] > h_hi:
                    problems.append(L("humid"))
                self.comfort_ok = not problems
                face = face_glyph(self.comfort_ok).replace("_", "__")
                if problems:
                    self.rows["mood"].set_label(f"{L('mood')}: {face} {', '.join(problems)}")
                else:
                    self.rows["mood"].set_label(f"{L('mood')}: {face} {L('comfortable')}")
            if d.get("batt") is not None:
                self.rows["batt"].set_label(f"{L('batt')}: {d['batt']}%")
        else:
            for key, item in self.rows.items():
                item.set_label(f"{L(key)}: —")
        kind = self.last_status[0]
        if kind == "updating":
            self.status_row.set_label(L("updating"))
        elif kind == "nodev":
            self.status_row.set_label(L("nodev_status"))
        elif kind == "ok":
            text = f"{L('updated')} {self.last_status[1]}"
            if self.last_status[2]:
                text += f", {L('synced')}"
            self.status_row.set_label(text)
        else:
            self.status_row.set_label(f"{L('no_link')} ({self.last_status[1]})")
        self.apply_tray()

    def apply_tray(self):
        d = self.last_data
        mode = config.get("tray")
        if mode in TRAY_MODES and mode != "icon" and d and "temp" in d:
            temp = f"{d['temp']:.1f}°"
            humi = f"{d['humi']}%"
            text = {
                "data": f"{temp}, {humi}",
                "data_face": f"{temp}, {humi}",
                "temp": temp,
                "humi": humi,
                "face": "",
            }[mode]
            face_kind = None
            if mode in ("data_face", "face"):
                if config.get("face") == "text":
                    glyph = FACES["happy" if self.comfort_ok else "sad"]["text"]
                    text = f"{text} {glyph}".strip()
                else:
                    face_kind = "happy" if self.comfort_ok else "sad"
            svg = build_tray_svg(text, face_kind)
        else:
            svg = build_tray_svg("", None, clock=True)
        self._icon_seq += 1
        name = f"lywsd02-label-{self._icon_seq}"
        with open(os.path.join(ICON_DIR, f"{name}.svg"), "w") as f:
            f.write(svg)
        self.indicator.set_icon_full(name, "LYWSD02")
        stale = os.path.join(ICON_DIR, f"lywsd02-label-{self._icon_seq - 2}.svg")
        try:
            os.remove(stale)
        except FileNotFoundError:
            pass
        self.indicator.set_label("", "")

    def retranslate(self):
        self.refresh_item.set_label(L("refresh"))
        self.settings_item.set_label(L("settings"))
        self.quit_item.set_label(L("quit"))
        self.render()

    def apply_data(self, data):
        stamp = datetime.now().strftime("%H:%M:%S")
        data["at"] = time.monotonic()
        self.last_data = data
        self.last_status = ("ok", stamp, data.get("synced", False))
        self.render()
        print(f"poll ok {stamp}: {data}", flush=True)
        return False

    def apply_error(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.last_status = ("error", stamp)
        self.render()
        print(f"poll failed {stamp}: {message}", flush=True)
        return False

    def apply_no_device(self):
        self.last_status = ("nodev",)
        self.render()
        return False

    def request_sync(self):
        self.sync_flag = True
        self.last_status = ("updating",)
        self.render()
        self.wake.set()

    def on_refresh(self, _):
        self.last_status = ("updating",)
        self.render()
        self.wake.set()

    def on_settings(self, _):
        if self.settings:
            self.settings.present()
            return
        self.settings = SettingsWindow(self)
        self.settings.connect("destroy", self.on_settings_closed)
        self.settings.show_all()

    def on_settings_closed(self, _):
        self.settings = None

    def on_quit(self, _):
        self.stop = True
        self.wake.set()
        Gtk.main_quit()


def main():
    GLib.set_prgname("lywsd02-widget")
    GLib.set_application_name("LYWSD02 Widget")
    widget = Widget()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Gtk.main()
    return widget


if __name__ == "__main__":
    main()
