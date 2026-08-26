# LYWSD02MMC-widget

[Русская версия](README.ru.md)

Ubuntu (GNOME) tray widget for the Xiaomi LYWSD02MMC clock-hygrometer. A tray icon (or live readings right in the panel); clicking it opens a menu with data read from the device over Bluetooth LE:

- clock time and its drift from system time
- temperature
- humidity
- comfort — the same "face" the clock shows on its screen: happy when temperature and humidity are inside the comfort zone, sad with a reason (cold/hot/dry/humid) when not. The face can be shown as emoji (🙂/🙁) or exactly like on the clock: `(^_^)` and `(-‸-)` — the e-ink display has two eye variants (`^`/`-`) and two mouth variants (`_`/`‸`), no other states exist
- battery level

The default comfort zone is 19–27 °C and 20–85 % humidity (factory thresholds of miaomiaoce devices; the LYWSD02 has them hardcoded in firmware with no BLE configuration, so the widget mirrors the logic on its side). Thresholds can be changed in `~/.config/lywsd02-widget/config.json`, key `comfort`: `t_lo`, `t_hi`, `h_lo`, `h_hi`.

Polling runs every 10 minutes (configurable); the "Refresh now" item requests data immediately.

## Supported devices

The widget works with the family of e-ink clock-hygrometers made by Miaomiaoce (miaomiaoce.com) and sold under the Xiaomi / Mijia brands. Official names of the same hardware in different regions:

| Model | Official name |
|---|---|
| LYWSD02MMC | Xiaomi Temperature and Humidity Monitor Clock (global, BHR5435GL); 米家电子温湿度计Pro (China) |
| LYWSD02 | Mijia Temperature and Humidity Electronic Watch — first generation, same protocol |
| MHO-C303 | Miaomiaoce Smart Clock — alarm-clock sibling by the same manufacturer, same protocol |

The same hardware is sold in the West as the Adafruit "Bluetooth eInk Display Clock with Temperature Humidity Sensor" (Adafruit 5023). Built-in discovery finds devices named `LYWSD02*` and `MHO-C303`.

## Installation

### From the package (recommended)

Download the `.deb` from the [releases page](../../releases) and install it — dependencies are pulled from the Ubuntu repositories automatically:

```sh
sudo apt install ./lywsd02-widget_*_all.deb
```

Launch "LYWSD02 Widget" from the application grid, open Settings, find your clock with the scan button and optionally enable autostart.

### From source

```sh
git clone https://github.com/fildunsky/LYWSD02MMC-widget.git
cd LYWSD02MMC-widget
./install.sh
./run.sh
```

The script creates a `.venv` with [bleak](https://github.com/hbldh/bleak), fetches the `gir1.2-ayatanaappindicator3-0.1` typelib via `apt-get download` when the package is missing (no root needed) and installs the application menu entry and autostart.

Building the `.deb`: `./package/build-deb.sh [version]` — output goes to `dist/`.

### Windows

Download `lywsd02-widget.exe` from the [releases page](../../releases) and run it — no installation needed (Windows 10+ with a BLE adapter). Windows tray icons are square, so the tray shows the icon, the face, the temperature or the humidity, while full readings live in the tooltip and the menu. Settings, device discovery, time sync and autostart (registry Run key) work the same as on Linux; config lives in `%APPDATA%\lywsd02-widget\config.json`. SmartScreen may warn about the unsigned binary — choose "More info → Run anyway". The exe is built in CI by the `windows-build` workflow from `win/lywsd02_widget_win.py`.

## Requirements

- Ubuntu with GNOME and the `ubuntu-appindicators` extension enabled (on by default)
- A Bluetooth adapter with BLE

## Settings

The Settings menu item opens a window:

- **Language** — Russian or English, applied instantly
- **Device** — the button with the current MAC opens discovery: the widget scans the air and lists found devices with address and signal level (your clock is usually the closest one — stronger signal); clicking a row selects the device and polls it right away
- **Poll, min** — polling period
- **Time zone** — "System" or a fixed offset in the "(UTC+03:00) Moscow, Istanbul, Riyadh" format: a list searchable by city and offset, including fractional zones (India +05:30, Nepal +05:45, Iran +03:30 etc.); written to the clock on sync
- **Face** — emoji or text, like on the clock
- **Tray** — what to show in the panel: icon, data (`23.8°, 49%`), data + face (`23.8°, 49% (^_^)`), face, temperature or humidity
- **Start at login** — adds/removes the entry in `~/.config/autostart`
- **Auto time sync** — on every poll, when the clock drifts from the system by more than 10 seconds or the timezone differs (enabled by default)
- **Sync time now** — force-writes system time to the clock

Settings are stored in `~/.config/lywsd02-widget/config.json`. The `LYWSD02_MAC` and `LYWSD02_POLL` environment variables work as fallbacks when the config has no values.

## Protocol

Standard LYWSD02 GATT characteristics (service `EBE0CCB0-...`):

| UUID | Data |
|---|---|
| `EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6` | time: uint32 LE (unix) + int8 timezone offset |
| `EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6` | notify: int16 LE temperature ×0.01 °C + uint8 humidity % |
| `EBE0CCC4-7A0A-4B0C-8A1A-6FF2997DA3A6` | uint8 battery % |

The firmware stores the timezone as a single byte in whole hours, so out of the box the clock cannot display fractional zones. The widget works around it: the byte gets the offset rounded down to the whole hour, and the remainder (30/45 minutes) is added to the epoch being written — the display ends up showing correct local time.

## Uninstall

Package: `sudo apt remove lywsd02-widget`. Source install:

```sh
rm ~/.config/autostart/lywsd02-widget.desktop ~/.local/share/applications/lywsd02-widget.desktop
```
