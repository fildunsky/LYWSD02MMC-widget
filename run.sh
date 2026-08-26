#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
unset GTK_PATH GIO_MODULE_DIR GDK_PIXBUF_MODULE_FILE GTK_EXE_PREFIX GTK_IM_MODULE_FILE
case "$LD_LIBRARY_PATH" in *snap*) unset LD_LIBRARY_PATH ;; esac
if ! "$DIR/.venv/bin/python" -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')" 2>/dev/null; then
    export GI_TYPELIB_PATH="$DIR/vendor${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
fi
exec "$DIR/.venv/bin/python" "$DIR/lywsd02_widget.py" "$@"
