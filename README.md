# LYWSD02MMC-widget

[Русская версия](README.ru.md)

Cross-platform tray / menu bar widget for the Xiaomi LYWSD02MMC clock-hygrometer. Runs on **Linux** (Ubuntu/GNOME), **Windows** and **macOS**, talks to the clock over Bluetooth LE and shows:

- clock time and its drift from system time, with automatic and manual time sync
- temperature
- humidity
- comfort — the same "face" the clock shows on its screen: happy when temperature and humidity are inside the comfort zone, sad with a reason (cold/hot/dry/humid) when not. The face can be shown as emoji (🙂/🙁) or exactly like on the clock: `(^_^)` and `(-‸-)` — the e-ink display has two eye variants (`^`/`-`) and two mouth variants (`_`/`‸`), no other states exist
- battery level

The tray can show a regular icon or the readings themselves: data (`23.8°, 49%`), data + face, face only, temperature or humidity.

The default comfort zone is 19–27 °C and 20–85 % humidity (factory thresholds of miaomiaoce devices; the LYWSD02 has them hardcoded in firmware with no BLE configuration, so the widget mirrors the logic on its side). Thresholds can be changed in the config file, key `comfort`: `t_lo`, `t_hi`, `h_lo`, `h_hi`.

Polling runs every 10 minutes (configurable); the "Refresh now" item requests data immediately. Timezones are picked from a city-labelled list and include fractional ones (India +05:30, Nepal +05:45, Iran +03:30 etc.) — the stock firmware cannot display those on its own, the widget works around it (see Protocol). UI languages: Russian and English.

## Platforms at a glance

| | Linux | Windows | macOS |
|---|---|---|---|
| Package | `.deb` | portable `.exe` | `.app` in zip (Apple Silicon) |
| Tray / menu bar | icon or live text | square icon; full readings in tooltip and menu | icon or live text, color emoji included |
| Settings | window | window | submenus of the dropdown |
| Autostart | `~/.config/autostart` | registry Run key | LaunchAgent |
| Config | `~/.config/lywsd02-widget/` | `%APPDATA%\lywsd02-widget\` | `~/Library/Application Support/lywsd02-widget/` |

## Supported devices

The widget works with the family of e-ink clock-hygrometers made by Miaomiaoce (miaomiaoce.com) and sold under the Xiaomi / Mijia brands. Official names of the same hardware in different regions:

| Model | Official name |
|---|---|
| LYWSD02MMC | Xiaomi Temperature and Humidity Monitor Clock (global, BHR5435GL); 米家电子温湿度计Pro (China) |
| LYWSD02 | Mijia Temperature and Humidity Electronic Watch — first generation, same protocol |
| MHO-C303 | Miaomiaoce Smart Clock — alarm-clock sibling by the same manufacturer, same protocol |

The same hardware is sold in the West as the Adafruit "Bluetooth eInk Display Clock with Temperature Humidity Sensor" (Adafruit 5023). Built-in discovery finds devices named `LYWSD02*` and `MHO-C303`; pick yours by signal level. On macOS the system hides Bluetooth MAC addresses, so devices are identified by system UUIDs — the built-in scan handles that transparently.

## Installation

All downloads are on the [releases page](../../releases). A BLE-capable Bluetooth adapter is required on every platform.

### Ubuntu / Linux

```sh
sudo apt install ./lywsd02-widget_*_all.deb
```

Dependencies are pulled from the Ubuntu repositories automatically. Requires GNOME with the `ubuntu-appindicators` extension (enabled out of the box on Ubuntu). Launch "LYWSD02 Widget" from the application grid.

### Windows 10+

Download `lywsd02-widget.exe` and run it — no installation needed. SmartScreen may warn about the unsigned binary — choose "More info → Run anyway".

### macOS

Download `lywsd02-widget-macos-arm64.zip` (Apple Silicon), unzip and launch with right-click → Open (the app is unsigned), then allow Bluetooth access. On Intel Macs run from source:

```sh
pip3 install bleak rumps pillow && python3 mac/lywsd02_widget_mac.py
```

### From source (Linux)

```sh
git clone https://github.com/fildunsky/LYWSD02MMC-widget.git
cd LYWSD02MMC-widget
./install.sh
./run.sh
```

The script creates a `.venv` with [bleak](https://github.com/hbldh/bleak), fetches the `gir1.2-ayatanaappindicator3-0.1` typelib via `apt-get download` when the package is missing (no root needed) and installs the application menu entry and autostart.

Packaging: `./package/build-deb.sh [version]` builds the `.deb` into `dist/`; the `windows-build` and `macos-build` GitHub Actions workflows build `win/lywsd02_widget_win.py` and `mac/lywsd02_widget_mac.py` and attach the binaries to a release.

## Settings

The Settings item (a window on Linux/Windows, dropdown submenus on macOS):

- **Language** — Russian or English, applied instantly
- **Device** — discovery: the widget scans the air and lists found devices with address and signal level; picking one selects it and polls it right away
- **Poll** — polling period in minutes
- **Time zone** — "System" or a fixed offset in the "(UTC+03:00) Moscow, Istanbul, Riyadh" format, fractional zones included; written to the clock on sync
- **Face** — emoji or text, like on the clock
- **Tray** — what to show in the panel / menu bar
- **Start at login**
- **Auto time sync** — on every poll, when the clock drifts from the system by more than 10 seconds or the timezone differs (enabled by default)
- **Sync time now**

The `LYWSD02_MAC` and `LYWSD02_POLL` environment variables work as fallbacks when the config has no values.

## Protocol

Standard LYWSD02 GATT characteristics (service `EBE0CCB0-...`):

| UUID | Data |
|---|---|
| `EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6` | time: uint32 LE (unix) + int8 timezone offset |
| `EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6` | notify: int16 LE temperature ×0.01 °C + uint8 humidity % |
| `EBE0CCC4-7A0A-4B0C-8A1A-6FF2997DA3A6` | uint8 battery % |

The firmware stores the timezone as a single byte in whole hours, so out of the box the clock cannot display fractional zones. The widget works around it: the byte gets the offset rounded down to the whole hour, and the remainder (30/45 minutes) is added to the epoch being written — the display ends up showing correct local time.

## Uninstall

- Linux (package): `sudo apt remove lywsd02-widget`
- Linux (source): `rm ~/.config/autostart/lywsd02-widget.desktop ~/.local/share/applications/lywsd02-widget.desktop`
- Windows: delete the exe; autostart is removed by unchecking "Start at login" in Settings
- macOS: delete the app; autostart is removed by unchecking "Start at login" (LaunchAgent `org.lywsd02.widget`)
