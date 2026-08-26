#!/bin/sh
set -e
VERSION="${1:-1.0.0}"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$DIR/dist"
PKG="$OUT/lywsd02-widget_${VERSION}_all"

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/share/lywsd02-widget" \
    "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/scalable/apps"

cp "$DIR/lywsd02_widget.py" "$DIR/lywsd02-widget.svg" "$DIR/lywsd02-widget.desktop.in" \
    "$PKG/usr/share/lywsd02-widget/"

cat > "$PKG/usr/bin/lywsd02-widget" <<'EOF'
#!/bin/sh
exec python3 /usr/share/lywsd02-widget/lywsd02_widget.py "$@"
EOF
chmod 755 "$PKG/usr/bin/lywsd02-widget"

sed -e "s|@EXEC@|lywsd02-widget|" -e "s|@ICON@|/usr/share/lywsd02-widget/lywsd02-widget.svg|" \
    "$DIR/lywsd02-widget.desktop.in" > "$PKG/usr/share/applications/lywsd02-widget.desktop"
cp "$DIR/lywsd02-widget.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/lywsd02-widget.svg"

cat > "$PKG/DEBIAN/control" <<EOF
Package: lywsd02-widget
Version: $VERSION
Maintainer: fildunsky <filipp.dunsky@gmail.com>
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, python3-bleak, bluez
Description: Tray widget for the Xiaomi LYWSD02MMC BLE clock
 Shows time, temperature, humidity, battery and the comfort face
 from the Xiaomi LYWSD02MMC e-ink clock in the Ubuntu/GNOME tray.
 Includes time sync, timezone selection and device discovery.
EOF

dpkg-deb --build --root-owner-group "$PKG" > /dev/null
rm -rf "$PKG"
echo "$OUT/lywsd02-widget_${VERSION}_all.deb"
