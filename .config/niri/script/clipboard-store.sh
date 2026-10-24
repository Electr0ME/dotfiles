#!/bin/sh
# wl-paste supplies CLIPBOARD_STATE. Never persist marked secrets or empty selections.
case "${CLIPBOARD_STATE:-data}" in
    sensitive|nil|clear) exit 0 ;;
esac
umask 077
exec cliphist -max-items 200 store
