#!/usr/bin/env python3
"""Generate the local Mocha wallpaper; requires python-cairo (already installed)."""
from pathlib import Path
import cairo

W, H = 1920, 1080
surface = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
ctx = cairo.Context(surface)

def rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))

base = cairo.LinearGradient(0, 0, W, H)
base.add_color_stop_rgb(0, *rgb('11111b'))
base.add_color_stop_rgb(0.55, *rgb('1e1e2e'))
base.add_color_stop_rgb(1, *rgb('181825'))
ctx.set_source(base)
ctx.paint()

# Muted lavender glow, kept low-contrast behind windows.
glow = cairo.RadialGradient(1450, 280, 0, 1450, 280, 1050)
glow.add_color_stop_rgba(0, *rgb('cba6f7'), 0.12)
glow.add_color_stop_rgba(1, *rgb('cba6f7'), 0)
ctx.set_source(glow)
ctx.paint()

# Broad rolling silhouettes using only Mocha palette colors.
for y, color, alpha in [(710, '313244', 0.65), (830, '45475a', 0.28), (930, '11111b', 0.65)]:
    ctx.move_to(0, y)
    ctx.curve_to(520, y - 260, 1040, y + 230, W, y - 170)
    ctx.line_to(W, H)
    ctx.line_to(0, H)
    ctx.close_path()
    ctx.set_source_rgba(*rgb(color), alpha)
    ctx.fill()

# A fine accent along the horizon.
ctx.move_to(0, 710)
ctx.curve_to(520, 450, 1040, 940, W, 540)
ctx.set_source_rgba(*rgb('cba6f7'), 0.16)
ctx.set_line_width(1.5)
ctx.stroke()
surface.write_to_png(str(Path(__file__).with_name('mocha.png')))
