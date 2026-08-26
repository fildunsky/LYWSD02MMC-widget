import asyncio
import json
import os
import queue
import struct
import sys
import threading
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import ttk

import pystray
from PIL import Image, ImageDraw, ImageFont
from bleak import BleakClient, BleakScanner

SYNC_THRESHOLD = 10
DEVICE_NAMES = ("LYWSD02", "MHO-C303")
UUID_TIME = "EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6"
UUID_DATA = "EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6"
UUID_BATT = "EBE0CCC4-7A0A-4B0C-8A1A-6FF2997DA3A6"
CONFIG_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "lywsd02-widget", "config.json"
)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "LYWSD02Widget"

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
        "sync_now": "Синхронизировать время сейчас",
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
        "sync_now": "Sync time now",
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
        "tray_face": "face",
        "tray_temp": "temperature",
        "tray_humi": "humidity",
    },
}

TZ_OFFSETS = sorted(
    set(range(-720, 841, 60))
    | {-570, -210, -150, 210, 270, 330, 345, 390, 525, 570, 630, 765, 825}
)

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

FACES = {
    "happy": {"emoji": "🙂", "text": "(^_^)"},
    "sad": {"emoji": "🙁", "text": "(-‸-)"},
}

TRAY_MODES = ("icon", "face", "temp", "humi")


def default_lang():
    try:
        import locale

        lang = locale.getlocale()[0] or ""
    except Exception:
        lang = ""
    return "ru" if lang.lower().startswith(("ru", "russian")) else "en"


DEFAULTS = {
    "lang": default_lang(),
    "tz": "system",
    "autosync": True,
    "face": "emoji",
    "tray": "icon",
    "comfort": {"t_lo": 19.0, "t_hi": 27.0, "h_lo": 20.0, "h_hi": 85.0},
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


config = load_config()


def save_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def L(key):
    lang = config.get("lang", "en")
    return STRINGS.get(lang, STRINGS["en"]).get(key, key)


def offset_label(minutes):
    sign = "+" if minutes >= 0 else "-"
    m = abs(minutes)
    return f"UTC{sign}{m // 60:02d}:{m % 60:02d}"


def tz_entry_label(minutes):
    lang = config.get("lang", "en")
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


def face_glyph(happy):
    style = "text" if config.get("face") == "text" else "emoji"
    return FACES["happy" if happy else "sad"][style]


def autostart_enabled():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(enabled):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}"'
            else:
                cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except OSError:
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


def load_font(size):
    for name in ("seguisb.ttf", "segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_image(kind, size=64, happy=True):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 64.0
    if kind == "icon":
        col = (235, 235, 235, 255)
        draw.rounded_rectangle(
            [6 * s, 6 * s, 58 * s, 58 * s], radius=10 * s, outline=col, width=int(4 * s)
        )
        for x in (14, 23):
            draw.rounded_rectangle([x * s, 19 * s, (x + 6) * s, 34 * s], radius=2 * s, fill=col)
        draw.ellipse([33 * s, 22 * s, 38 * s, 27 * s], fill=col)
        draw.ellipse([33 * s, 29 * s, 38 * s, 34 * s], fill=col)
        draw.rounded_rectangle([40 * s, 19 * s, 46 * s, 34 * s], radius=2 * s, fill=col)
        draw.rounded_rectangle([14 * s, 41 * s, 28 * s, 46 * s], radius=2.5 * s, fill=col)
        draw.rounded_rectangle([33 * s, 41 * s, 47 * s, 46 * s], radius=2.5 * s, fill=col)
    elif kind == "face":
        draw.ellipse([4 * s, 4 * s, 60 * s, 60 * s], fill=(252, 194, 27, 255))
        eye = (70, 52, 42, 255)
        draw.ellipse([17 * s, 20 * s, 26 * s, 29 * s], fill=eye)
        draw.ellipse([38 * s, 20 * s, 47 * s, 29 * s], fill=eye)
        if happy:
            draw.arc([16 * s, 22 * s, 48 * s, 50 * s], start=20, end=160, fill=eye, width=int(5 * s))
        else:
            draw.arc([16 * s, 38 * s, 48 * s, 62 * s], start=200, end=340, fill=eye, width=int(5 * s))
    else:
        font_size = int(size * 0.56)
        font = load_font(font_size)
        while font_size > 8:
            bbox = draw.textbbox((0, 0), kind, font=font)
            if bbox[2] - bbox[0] <= size - 2:
                break
            font_size -= 2
            font = load_font(font_size)
        bbox = draw.textbbox((0, 0), kind, font=font)
        x = (size - (bbox[2] - bbox[0])) / 2 - bbox[0]
        y = (size - (bbox[3] - bbox[1])) / 2 - bbox[1]
        draw.text((x, y), kind, font=font, fill=(240, 240, 240, 255))
    return img


class App:
    def __init__(self):
        self.last_data = None
        self.last_status = ("updating",)
        self.comfort_ok = True
        self.problems = []
        self.settings = None
        self.wake = threading.Event()
        self.sync_flag = False
        self.stop = False
        self.ui_queue = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("LYWSD02")

        item = pystray.MenuItem
        self.icon = pystray.Icon(
            "lywsd02-widget",
            make_image("icon"),
            "LYWSD02",
            menu=pystray.Menu(
                item(lambda i: self.row_time(), None, enabled=False),
                item(lambda i: self.row_drift(), None, enabled=False),
                item(lambda i: self.row_temp(), None, enabled=False),
                item(lambda i: self.row_humi(), None, enabled=False),
                item(lambda i: self.row_mood(), None, enabled=False),
                item(lambda i: self.row_batt(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                item(lambda i: self.row_status(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                item(lambda i: L("refresh"), self.on_refresh),
                item(lambda i: L("settings"), lambda: self.ui_call(self.open_settings)),
                item(lambda i: L("quit"), self.on_quit),
            ),
        )

        self.worker = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker.start()

    def ui_call(self, fn, *args):
        self.ui_queue.put((fn, args))

    def pump(self):
        while True:
            try:
                fn, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception:
                pass
        self.root.after(100, self.pump)

    def dash_row(self, key):
        return f"{L(key)}: —"

    def row_time(self):
        d = self.last_data
        if not d:
            return self.dash_row("time")
        watch = datetime.fromtimestamp(d["epoch"], timezone(timedelta(hours=d["tz"])))
        return f"{L('time')}: {watch.strftime('%H:%M:%S')}"

    def row_drift(self):
        d = self.last_data
        if not d:
            return self.dash_row("drift")
        return f"{L('drift')}: {d['drift']:+d} {L('sec')}"

    def row_temp(self):
        d = self.last_data
        if not d or "temp" not in d:
            return self.dash_row("temp")
        return f"{L('temp')}: {d['temp']:.1f} °C"

    def row_humi(self):
        d = self.last_data
        if not d or "temp" not in d:
            return self.dash_row("humi")
        return f"{L('humi')}: {d['humi']}%"

    def row_mood(self):
        d = self.last_data
        if not d or "temp" not in d:
            return self.dash_row("mood")
        face = face_glyph(self.comfort_ok)
        detail = ", ".join(self.problems) if self.problems else L("comfortable")
        return f"{L('mood')}: {face} {detail}"

    def row_batt(self):
        d = self.last_data
        if not d or d.get("batt") is None:
            return self.dash_row("batt")
        return f"{L('batt')}: {d['batt']}%"

    def row_status(self):
        kind = self.last_status[0]
        if kind == "updating":
            return L("updating")
        if kind == "nodev":
            return L("nodev_status")
        if kind == "ok":
            text = f"{L('updated')} {self.last_status[1]}"
            if self.last_status[2]:
                text += f", {L('synced')}"
            return text
        return f"{L('no_link')} ({self.last_status[1]})"

    def worker_loop(self):
        while not self.stop:
            sync = self.sync_flag
            self.sync_flag = False
            mac = device_mac()
            if mac:
                try:
                    data = asyncio.run(poll_device(mac, sync))
                    self.apply_data(data)
                except Exception as exc:
                    self.apply_error(str(exc))
            else:
                self.last_status = ("nodev",)
                self.refresh_tray()
            self.wake.wait(poll_seconds())
            self.wake.clear()

    def apply_data(self, data):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.last_data = data
        self.last_status = ("ok", stamp, data.get("synced", False))
        if "temp" in data:
            t_lo, t_hi, h_lo, h_hi = comfort_range()
            self.problems = []
            if data["temp"] < t_lo:
                self.problems.append(L("cold"))
            if data["temp"] > t_hi:
                self.problems.append(L("hot"))
            if data["humi"] < h_lo:
                self.problems.append(L("dry"))
            if data["humi"] > h_hi:
                self.problems.append(L("humid"))
            self.comfort_ok = not self.problems
        self.refresh_tray()

    def apply_error(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.last_status = ("error", stamp)
        self.refresh_tray()

    def refresh_tray(self):
        d = self.last_data
        mode = config.get("tray")
        if mode not in TRAY_MODES:
            mode = "icon"
        if mode == "icon" or not d or "temp" not in d:
            self.icon.icon = make_image("icon")
        elif mode == "face":
            style = config.get("face")
            if style == "text":
                self.icon.icon = make_image(FACES["happy" if self.comfort_ok else "sad"]["text"])
            else:
                self.icon.icon = make_image("face", happy=self.comfort_ok)
        elif mode == "temp":
            self.icon.icon = make_image(f"{round(d['temp'])}°")
        else:
            self.icon.icon = make_image(f"{d['humi']}%")
        if d and "temp" in d:
            title = f"{d['temp']:.1f}°, {d['humi']}% {face_glyph(self.comfort_ok)}"
            if d.get("batt") is not None:
                title += f" · {L('batt')}: {d['batt']}%"
            self.icon.title = title[:127]
        else:
            self.icon.title = "LYWSD02"
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def request_sync(self):
        self.sync_flag = True
        self.last_status = ("updating",)
        self.refresh_tray()
        self.wake.set()

    def on_refresh(self):
        self.last_status = ("updating",)
        self.refresh_tray()
        self.wake.set()

    def on_quit(self):
        self.stop = True
        self.wake.set()
        self.icon.stop()
        self.ui_call(self.root.quit)

    def open_settings(self):
        if self.settings and self.settings.winfo_exists():
            self.settings.deiconify()
            self.settings.lift()
            return
        win = tk.Toplevel(self.root)
        self.settings = win
        win.title(L("settings"))
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=12)
        frame.grid(sticky="nsew")

        ttk.Label(frame, text=L("lang")).grid(row=0, column=0, sticky="w", pady=4)
        lang_combo = ttk.Combobox(frame, state="readonly", values=["Русский", "English"], width=28)
        lang_combo.current(0 if config.get("lang") == "ru" else 1)
        lang_combo.grid(row=0, column=1, pady=4)

        def on_lang(_):
            config["lang"] = "ru" if lang_combo.current() == 0 else "en"
            save_config()
            self.refresh_tray()
            win.destroy()
            self.open_settings()

        lang_combo.bind("<<ComboboxSelected>>", on_lang)

        ttk.Label(frame, text=L("device")).grid(row=1, column=0, sticky="w", pady=4)
        device_btn = ttk.Button(
            frame, text=device_mac() or L("no_device"), command=lambda: self.open_scan(win, device_btn)
        )
        device_btn.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text=L("poll")).grid(row=2, column=0, sticky="w", pady=4)
        poll_var = tk.IntVar(value=poll_seconds() // 60)
        poll_spin = ttk.Spinbox(frame, from_=1, to=120, textvariable=poll_var, width=6)
        poll_spin.grid(row=2, column=1, sticky="w", pady=4)

        def on_poll(*_):
            try:
                config["poll"] = max(1, int(poll_var.get())) * 60
                save_config()
            except Exception:
                pass

        poll_var.trace_add("write", on_poll)

        ttk.Label(frame, text=L("tz")).grid(row=3, column=0, sticky="w", pady=4)
        tz_values = [f"{L('tz_system')} ({offset_label(system_tz_minutes())})"]
        tz_values += [tz_entry_label(m) for m in TZ_OFFSETS]
        tz_combo = ttk.Combobox(frame, state="readonly", values=tz_values, width=34)
        active = config.get("tz", "system")
        if active == "system":
            tz_combo.current(0)
        else:
            try:
                tz_combo.current(1 + TZ_OFFSETS.index(tz_config_minutes(active)))
            except ValueError:
                tz_combo.current(0)
        tz_combo.grid(row=3, column=1, pady=4)

        def on_tz(_):
            idx = tz_combo.current()
            value = "system" if idx == 0 else TZ_OFFSETS[idx - 1]
            if value != config.get("tz"):
                config["tz"] = value
                save_config()
                self.request_sync()
                note_var.set(L("sync_requested"))

        tz_combo.bind("<<ComboboxSelected>>", on_tz)

        ttk.Label(frame, text=L("face_style")).grid(row=4, column=0, sticky="w", pady=4)
        face_combo = ttk.Combobox(
            frame,
            state="readonly",
            values=[FACES["happy"]["emoji"], FACES["happy"]["text"]],
            width=10,
        )
        face_combo.current(1 if config.get("face") == "text" else 0)
        face_combo.grid(row=4, column=1, sticky="w", pady=4)

        def on_face(_):
            config["face"] = "text" if face_combo.current() == 1 else "emoji"
            save_config()
            self.refresh_tray()

        face_combo.bind("<<ComboboxSelected>>", on_face)

        ttk.Label(frame, text=L("tray_mode")).grid(row=5, column=0, sticky="w", pady=4)
        tray_combo = ttk.Combobox(
            frame,
            state="readonly",
            values=[L(f"tray_{m}") for m in TRAY_MODES],
            width=16,
        )
        active_tray = config.get("tray")
        tray_combo.current(TRAY_MODES.index(active_tray) if active_tray in TRAY_MODES else 0)
        tray_combo.grid(row=5, column=1, sticky="w", pady=4)

        def on_tray(_):
            config["tray"] = TRAY_MODES[tray_combo.current()]
            save_config()
            self.refresh_tray()

        tray_combo.bind("<<ComboboxSelected>>", on_tray)

        auto_var = tk.BooleanVar(value=autostart_enabled())

        def on_autostart():
            try:
                set_autostart(auto_var.get())
            except Exception:
                pass

        ttk.Checkbutton(frame, text=L("autostart"), variable=auto_var, command=on_autostart).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=4
        )

        sync_var = tk.BooleanVar(value=bool(config.get("autosync")))

        def on_autosync():
            config["autosync"] = sync_var.get()
            save_config()

        ttk.Checkbutton(frame, text=L("autosync"), variable=sync_var, command=on_autosync).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=4
        )

        note_var = tk.StringVar(value="")

        def on_sync():
            self.request_sync()
            note_var.set(L("sync_requested"))

        ttk.Button(frame, text=L("sync_now"), command=on_sync).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=6
        )
        ttk.Label(frame, textvariable=note_var, foreground="#777777").grid(
            row=9, column=0, columnspan=2, sticky="w"
        )

    def open_scan(self, parent, device_btn):
        win = tk.Toplevel(parent)
        win.title(L("scan_title"))
        win.geometry("420x340")
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill="both", expand=True)
        status_var = tk.StringVar(value=L("scanning"))
        ttk.Label(frame, textvariable=status_var).pack(anchor="w")
        listbox = tk.Listbox(frame)
        listbox.pack(fill="both", expand=True, pady=6)
        rows = []
        stop = threading.Event()
        win.protocol("WM_DELETE_WINDOW", lambda: (stop.set(), win.destroy()))

        def add_row(mac, name, rssi):
            rows.append(mac)
            listbox.insert("end", f"{name}   {mac}   {rssi} dBm")

        def on_pick(_):
            sel = listbox.curselection()
            if not sel:
                return
            config["mac"] = rows[sel[0]]
            save_config()
            device_btn.config(text=rows[sel[0]])
            self.on_refresh()
            stop.set()
            win.destroy()

        listbox.bind("<Double-Button-1>", on_pick)
        listbox.bind("<Return>", on_pick)

        def scan_worker():
            found = {}

            def on_adv(device, adv):
                name = adv.local_name or device.name or ""
                if not any(n in name for n in DEVICE_NAMES):
                    return
                if device.address in found or stop.is_set():
                    return
                found[device.address] = name
                self.ui_call(add_row, device.address, name, adv.rssi)

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
                    self.ui_call(status_var.set, str(exc)[:120])
                return
            if not stop.is_set():
                text = f"{L('scan_found')}: {len(found)}" if found else L("scan_none")
                self.ui_call(status_var.set, text)

        threading.Thread(target=scan_worker, daemon=True).start()


def main():
    app = App()
    threading.Thread(target=app.icon.run, daemon=True).start()
    app.root.after(100, app.pump)
    app.root.mainloop()


if __name__ == "__main__":
    main()
