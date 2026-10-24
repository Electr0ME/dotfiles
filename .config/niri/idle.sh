#!/bin/sh
# Lock after 10 minutes; switch displays off after 15 minutes. No automatic suspend.
exec swayidle -w \
    timeout 600 'sh "$HOME/.config/niri/lock.sh"' \
    timeout 900 'niri msg action power-off-monitors' \
    resume 'niri msg action power-on-monitors' \
    before-sleep 'sh "$HOME/.config/niri/lock.sh"' \
    lock 'sh "$HOME/.config/niri/lock.sh"'
