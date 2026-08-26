#!/bin/sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

python3 -m venv --system-site-packages "$DIR/.venv"
"$DIR/.venv/bin/pip" -q install bleak pillow

if ! python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')" 2>/dev/null; then
    mkdir -p "$DIR/vendor"
    if [ ! -f "$DIR/vendor/AyatanaAppIndicator3-0.1.typelib" ]; then
        tmp="$(mktemp -d)"
        (
            cd "$tmp"
            apt-get download gir1.2-ayatanaappindicator3-0.1
            dpkg-deb -x gir1.2-ayatanaappindicator3-0.1_*.deb x
            find x -name '*.typelib' -exec cp {} "$DIR/vendor/" \;
        )
        rm -rf "$tmp"
    fi
fi

mkdir -p "$HOME/.local/share/applications" "$HOME/.config/autostart"
sed -e "s|@EXEC@|$DIR/run.sh|" -e "s|@ICON@|$DIR/lywsd02-widget.svg|" \
    "$DIR/lywsd02-widget.desktop.in" > "$HOME/.local/share/applications/lywsd02-widget.desktop"
cp "$HOME/.local/share/applications/lywsd02-widget.desktop" "$HOME/.config/autostart/lywsd02-widget.desktop"

echo "Готово. Запуск: $DIR/run.sh"
