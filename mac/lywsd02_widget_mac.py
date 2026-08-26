import asyncio
import json
import os
import plistlib
import struct
import sys
import threading
from datetime import datetime, timedelta, timezone

import rumps

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = ImageDraw = None

from bleak import BleakClient, BleakScanner

SYNC_THRESHOLD = 10
DEVICE_NAMES = ("LYWSD02", "MHO-C303")
UUID_TIME = "EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6"
UUID_DATA = "EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6"
UUID_BATT = "EBE0CCC4-7A0A-4B0C-8A1A-6FF2997DA3A6"
APP_SUPPORT = os.path.expanduser("~/Library/Application Support/lywsd02-widget")
CONFIG_PATH = os.path.join(APP_SUPPORT, "config.json")
LAUNCH_AGENT = os.path.expanduser("~/Library/LaunchAgents/org.lywsd02.widget.plist")

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
        "scan": "Найти часы",
        "scanning": "Идёт поиск…",
        "scan_none": "Ничего не найдено",
        "poll": "Опрос",
        "min": "мин",
        "tray_mode": "В строке меню",
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
        "sync_now": "Sync time now",
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
        "scan": "Find devices",
        "scanning": "Scanning…",
        "scan_none": "Nothing found",
        "poll": "Poll",
        "min": "min",
        "tray_mode": "Menu bar",
        "tray_icon": "icon",
        "tray_data": "data",
        "tray_data_face": "data + face",
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

TRAY_MODES = ("icon", "data", "data_face", "face", "temp", "humi")
POLL_PRESETS = (1, 2, 5, 10, 15, 30, 60)


def default_lang():
    try:
        import locale

        lang = locale.getlocale()[0] or ""
    except Exception:
        lang = ""
    return "ru" if lang.lower().startswith("ru") else "en"


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
    return os.path.exists(LAUNCH_AGENT)


def set_autostart(enabled):
    if enabled:
        os.makedirs(os.path.dirname(LAUNCH_AGENT), exist_ok=True)
        if getattr(sys, "frozen", False):
            args = [sys.executable]
        else:
            args = [sys.executable, os.path.abspath(__file__)]
        payload = {"Label": "org.lywsd02.widget", "ProgramArguments": args, "RunAtLoad": True}
        with open(LAUNCH_AGENT, "wb") as f:
            plistlib.dump(payload, f)
    else:
        try:
            os.remove(LAUNCH_AGENT)
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


def make_image(kind, size=64, happy=True, color=(0, 0, 0, 255)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 64.0
    if kind == "icon":
        draw.rounded_rectangle(
            [6 * s, 6 * s, 58 * s, 58 * s], radius=10 * s, outline=color, width=int(4 * s)
        )
        for x in (14, 23):
            draw.rounded_rectangle([x * s, 19 * s, (x + 6) * s, 34 * s], radius=2 * s, fill=color)
        draw.ellipse([33 * s, 22 * s, 38 * s, 27 * s], fill=color)
        draw.ellipse([33 * s, 29 * s, 38 * s, 34 * s], fill=color)
        draw.rounded_rectangle([40 * s, 19 * s, 46 * s, 34 * s], radius=2 * s, fill=color)
        draw.rounded_rectangle([14 * s, 41 * s, 28 * s, 46 * s], radius=2.5 * s, fill=color)
        draw.rounded_rectangle([33 * s, 41 * s, 47 * s, 46 * s], radius=2.5 * s, fill=color)
    else:
        draw.ellipse([4 * s, 4 * s, 60 * s, 60 * s], fill=(252, 194, 27, 255))
        eye = (70, 52, 42, 255)
        draw.ellipse([17 * s, 20 * s, 26 * s, 29 * s], fill=eye)
        draw.ellipse([38 * s, 20 * s, 47 * s, 29 * s], fill=eye)
        if happy:
            draw.arc([16 * s, 22 * s, 48 * s, 50 * s], start=20, end=160, fill=eye, width=int(5 * s))
        else:
            draw.arc([16 * s, 38 * s, 48 * s, 62 * s], start=200, end=340, fill=eye, width=int(5 * s))
    return img


def menubar_icon_path():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    bundled = os.path.join(base, "menubar.png")
    if os.path.exists(bundled):
        return bundled
    if Image is None:
        return None
    try:
        os.makedirs(APP_SUPPORT, exist_ok=True)
        path = os.path.join(APP_SUPPORT, "menubar.png")
        make_image("icon", 44).save(path)
        return path
    except Exception:
        return None


class TrayApp(rumps.App):
    def __init__(self):
        super().__init__("LYWSD02", icon=None, template=True, quit_button=None)
        self.last_data = None
        self.last_status = ("updating",)
        self.comfort_ok = True
        self.problems = []
        self.dirty = True
        self.scan_state = None
        self.scan_results = []
        self.wake = threading.Event()
        self.sync_flag = False
        self.icon_file = menubar_icon_path()
        self.rebuild_menu()
        self.timer = rumps.Timer(self.on_tick, 1)
        self.timer.start()
        self.worker = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker.start()

    def rebuild_menu(self):
        self.menu.clear()
        self.rows = {}
        items = []
        for key in ("time", "drift", "temp", "humi", "mood", "batt"):
            row = rumps.MenuItem(f"{L(key)}: —")
            self.rows[key] = row
            items.append(row)
        items.append(None)
        self.status_row = rumps.MenuItem(L("updating"))
        items.append(self.status_row)
        items.append(None)
        items.append(rumps.MenuItem(L("refresh"), callback=self.on_refresh))
        items.append(self.build_settings_menu())
        items.append(rumps.MenuItem(L("quit"), callback=self.on_quit))
        self.menu = items
        self.dirty = True

    def build_settings_menu(self):
        settings = rumps.MenuItem(L("settings"))

        lang_menu = rumps.MenuItem(L("lang"))
        for lid, title in (("ru", "Русский"), ("en", "English")):
            item = rumps.MenuItem(title, callback=self.make_setter("lang", lid, rebuild=True))
            item.state = 1 if config.get("lang") == lid else 0
            lang_menu.add(item)
        settings.add(lang_menu)

        device_menu = rumps.MenuItem(L("device"))
        scan_title = L("scanning") if self.scan_state == "running" else L("scan")
        device_menu.add(rumps.MenuItem(scan_title, callback=self.on_scan))
        current = device_mac()
        if self.scan_state == "done" and not self.scan_results:
            device_menu.add(rumps.MenuItem(L("scan_none")))
        for mac, name, rssi in self.scan_results:
            item = rumps.MenuItem(f"{name}  {rssi} dBm  {mac}", callback=self.make_device_setter(mac))
            item.state = 1 if mac == current else 0
            device_menu.add(item)
        if current and current not in [m for m, _, _ in self.scan_results]:
            item = rumps.MenuItem(current)
            item.state = 1
            device_menu.add(item)
        settings.add(device_menu)

        poll_menu = rumps.MenuItem(f"{L('poll')}, {L('min')}")
        for minutes in POLL_PRESETS:
            item = rumps.MenuItem(str(minutes), callback=self.make_setter("poll", minutes * 60, rebuild=True))
            item.state = 1 if poll_seconds() == minutes * 60 else 0
            poll_menu.add(item)
        settings.add(poll_menu)

        tz_menu = rumps.MenuItem(L("tz"))
        active = config.get("tz", "system")
        item = rumps.MenuItem(
            f"{L('tz_system')} ({offset_label(system_tz_minutes())})",
            callback=self.make_tz_setter("system"),
        )
        item.state = 1 if active == "system" else 0
        tz_menu.add(item)
        active_min = None if active == "system" else tz_config_minutes(active)
        for m in TZ_OFFSETS:
            item = rumps.MenuItem(tz_entry_label(m), callback=self.make_tz_setter(m))
            item.state = 1 if active_min == m else 0
            tz_menu.add(item)
        settings.add(tz_menu)

        face_menu = rumps.MenuItem(L("face_style"))
        for fid, title in (("emoji", FACES["happy"]["emoji"]), ("text", FACES["happy"]["text"])):
            item = rumps.MenuItem(title, callback=self.make_setter("face", fid, rebuild=True))
            item.state = 1 if config.get("face", "emoji") == fid else 0
            face_menu.add(item)
        settings.add(face_menu)

        tray_menu = rumps.MenuItem(L("tray_mode"))
        active_tray = config.get("tray") if config.get("tray") in TRAY_MODES else "icon"
        for mode in TRAY_MODES:
            item = rumps.MenuItem(L(f"tray_{mode}"), callback=self.make_setter("tray", mode, rebuild=True))
            item.state = 1 if active_tray == mode else 0
            tray_menu.add(item)
        settings.add(tray_menu)

        autostart_item = rumps.MenuItem(L("autostart"), callback=self.on_autostart)
        autostart_item.state = 1 if autostart_enabled() else 0
        settings.add(autostart_item)

        autosync_item = rumps.MenuItem(L("autosync"), callback=self.on_autosync)
        autosync_item.state = 1 if config.get("autosync") else 0
        settings.add(autosync_item)

        settings.add(rumps.MenuItem(L("sync_now"), callback=self.on_sync_now))
        return settings

    def make_setter(self, key, value, rebuild=False):
        def handler(_):
            config[key] = value
            save_config()
            if rebuild:
                self.rebuild_menu()
            self.dirty = True

        return handler

    def make_device_setter(self, mac):
        def handler(_):
            config["mac"] = mac
            save_config()
            self.rebuild_menu()
            self.on_refresh(None)

        return handler

    def make_tz_setter(self, value):
        def handler(_):
            if value != config.get("tz"):
                config["tz"] = value
                save_config()
                self.rebuild_menu()
                self.request_sync()

        return handler

    def on_autostart(self, item):
        set_autostart(not autostart_enabled())
        item.state = 1 if autostart_enabled() else 0

    def on_autosync(self, item):
        config["autosync"] = not config.get("autosync")
        save_config()
        item.state = 1 if config.get("autosync") else 0

    def on_sync_now(self, _):
        self.request_sync()

    def on_scan(self, _):
        if self.scan_state == "running":
            return
        self.scan_state = "running"
        self.scan_results = []
        self.rebuild_menu()
        threading.Thread(target=self.scan_worker, daemon=True).start()

    def scan_worker(self):
        found = {}

        def on_adv(device, adv):
            name = adv.local_name or device.name or ""
            if not any(n in name for n in DEVICE_NAMES):
                return
            if device.address in found:
                return
            found[device.address] = (name, adv.rssi)

        async def run():
            scanner = BleakScanner(detection_callback=on_adv)
            await scanner.start()
            await asyncio.sleep(12)
            await scanner.stop()

        try:
            asyncio.run(run())
        except Exception:
            pass
        self.scan_results = [(mac, name, rssi) for mac, (name, rssi) in found.items()]
        self.scan_state = "rebuild"

    def request_sync(self):
        self.sync_flag = True
        self.last_status = ("updating",)
        self.dirty = True
        self.wake.set()

    def on_refresh(self, _):
        self.last_status = ("updating",)
        self.dirty = True
        self.wake.set()

    def on_quit(self, _):
        rumps.quit_application()

    def worker_loop(self):
        while True:
            sync = self.sync_flag
            self.sync_flag = False
            mac = device_mac()
            if mac:
                try:
                    data = asyncio.run(poll_device(mac, sync))
                    self.apply_data(data)
                except Exception:
                    self.last_status = ("error", datetime.now().strftime("%H:%M:%S"))
                    self.dirty = True
            else:
                self.last_status = ("nodev",)
                self.dirty = True
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
        self.dirty = True

    def on_tick(self, _):
        if self.scan_state == "rebuild":
            self.scan_state = "done"
            self.rebuild_menu()
        if not self.dirty:
            return
        self.dirty = False
        self.render_rows()
        self.apply_tray()

    def render_rows(self):
        d = self.last_data
        if d:
            watch = datetime.fromtimestamp(d["epoch"], timezone(timedelta(hours=d["tz"])))
            self.rows["time"].title = f"{L('time')}: {watch.strftime('%H:%M:%S')}"
            self.rows["drift"].title = f"{L('drift')}: {d['drift']:+d} {L('sec')}"
            if "temp" in d:
                self.rows["temp"].title = f"{L('temp')}: {d['temp']:.1f} °C"
                self.rows["humi"].title = f"{L('humi')}: {d['humi']}%"
                face = face_glyph(self.comfort_ok)
                detail = ", ".join(self.problems) if self.problems else L("comfortable")
                self.rows["mood"].title = f"{L('mood')}: {face} {detail}"
            if d.get("batt") is not None:
                self.rows["batt"].title = f"{L('batt')}: {d['batt']}%"
        else:
            for key, row in self.rows.items():
                row.title = f"{L(key)}: —"
        kind = self.last_status[0]
        if kind == "updating":
            self.status_row.title = L("updating")
        elif kind == "nodev":
            self.status_row.title = L("nodev_status")
        elif kind == "ok":
            text = f"{L('updated')} {self.last_status[1]}"
            if self.last_status[2]:
                text += f", {L('synced')}"
            self.status_row.title = text
        else:
            self.status_row.title = f"{L('no_link')} ({self.last_status[1]})"

    def apply_tray(self):
        d = self.last_data
        mode = config.get("tray")
        if mode not in TRAY_MODES:
            mode = "icon"
        if mode == "icon" or not d or "temp" not in d:
            if self.icon_file:
                self.icon = self.icon_file
                self.title = None
            else:
                self.icon = None
                self.title = "LYWSD02"
            return
        temp = f"{d['temp']:.1f}°"
        humi = f"{d['humi']}%"
        face = face_glyph(self.comfort_ok)
        text = {
            "data": f"{temp}, {humi}",
            "data_face": f"{temp}, {humi} {face}",
            "face": face,
            "temp": temp,
            "humi": humi,
        }[mode]
        self.icon = None
        self.title = text


def main():
    TrayApp().run()


if __name__ == "__main__":
    main()
