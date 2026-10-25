# Niri dotfiles

本仓库保存当前 Niri 桌面相关配置的快照，按用户主目录的结构组织。

## 备份内容

- `.config/niri/`：主配置、显示器配置、窗口规则、快捷键、会话/锁屏/空闲脚本、辅助脚本，以及 `wallpapers/wallpaper.png`（当前壁纸）。
- `.config/waybar/`：状态栏配置与样式。
- `.config/waybar/scripts/`：自定义 CPU 用量模块和 mako 勿扰状态模块。
- `.config/mako/`：mako 通知守护进程配置（已替代 SwayNC）。
- `.config/fastfetch/`：fastfetch 系统信息展示配置。
- `.config/swaylock/`：锁屏配置。
- `.config/fuzzel/`：应用启动器配置。
- `.config/kitty/`：终端配置与 Catppuccin Mocha 主题（不包含历史 `.bak-*` 文件）。
- `.config/systemd/user/niri-clipboard.service`：Niri 会话剪贴板服务。

不包含历史 `backups/`、Python 缓存、运行日志或剪贴板历史。原有配置未作修改。

> 通知已从 SwayNC 切换到 mako。mako 没有独立的通知中心面板；`Mod+Shift+N` 或点击 Waybar 通知图标可切换勿扰模式。

> `~/.config/niri/wallpapers/` 只保存当前壁纸 `wallpaper.png`。`Mod+X` → “切换壁纸”从 `~/Pictures/Wallpapers/` 选择图片时，会先用 ImageMagick 将其转换为 PNG 并替换该文件，再重启 swaybg；会话启动和锁屏也直接使用这个文件。壁纸通过 layer rule 固定在 Overview 的 backdrop 中，不随工作区缩放。

## 恢复

先备份目标机器现有配置，再在仓库根目录执行（将覆盖同名文件）：

```sh
mkdir -p "$HOME/.config"
cp -a .config/. "$HOME/.config/"
systemctl --user daemon-reload
```

配置使用 `~`、`sh -c` 和 systemd 的 `%h` 等可移植路径，不再依赖固定的用户主目录；`outputs.kdl` 仍需要按显示器情况调整。

## 依赖

以下为 Arch Linux 官方仓库中的包名：

```sh
sudo pacman -S --needed \
  niri xwayland-satellite \
  waybar mako swaybg swayidle swaylock \
  fuzzel kitty nautilus polkit-gnome \
  xdg-desktop-portal xdg-desktop-portal-gnome \
  pipewire pipewire-pulse wireplumber pavucontrol \
  networkmanager nm-connection-editor \
  fcitx5 fcitx5-gtk fcitx5-qt \
  imagemagick wl-clipboard cliphist python libnotify playerctl \
  ttf-jetbrains-mono-nerd noto-fonts-cjk papirus-icon-theme
```

- 桌面会话：niri、waybar、mako、swaybg、swayidle、swaylock、fuzzel、kitty、polkit-gnome、xdg-desktop-portal(-gnome)；xwayland-satellite 用于运行 X11 应用。
- 音频与网络：pipewire、pipewire-pulse、wireplumber、pavucontrol、networkmanager、nm-connection-editor。
- 输入法：fcitx5、fcitx5-gtk、fcitx5-qt；中文输入另需 fcitx5-chinese-addons，图形配置工具为 fcitx5-configtool。
- 脚本与工具：python（仅使用标准库）、imagemagick（壁纸转换）、wl-clipboard、cliphist、libnotify（可选，用于 notify-send）、playerctl（媒体键），以及 gawk、procps-ng、util-linux 等基础工具。
- 字体与主题：ttf-jetbrains-mono-nerd、noto-fonts-cjk、papirus-icon-theme；GTK 主题 `catppuccin-mocha-mauve-standard+default` 需从 AUR 或源码安装到 `~/.local/share/themes`，缺失时回退默认主题。
- 可选：nautilus（`Mod+E`）、fastfetch、xdg-desktop-portal-gtk。

不需要 swaync、brightnessctl 或 grim；截图与 Overview 等功能由 niri 自身提供。本仓库不安装软件，也不自动启用服务。
