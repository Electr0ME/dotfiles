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

> `~/.config/niri/wallpapers/` 只保存当前壁纸 `wallpaper.png`。`Mod+X` → “切换壁纸”从 `~/Pictures/Wallpapers/` 选择图片时，会先用 ImageMagick 将其转换为 PNG 并替换该文件，再重启 swaybg；会话启动和锁屏也直接使用这个文件。

## 恢复

先备份目标机器现有配置，再在仓库根目录执行（将覆盖同名文件）：

```sh
mkdir -p "$HOME/.config"
cp -a .config/. "$HOME/.config/"
systemctl --user daemon-reload
```

配置使用 `~`、`sh -c` 和 systemd 的 `%h` 等可移植路径，不再依赖固定的用户主目录；`outputs.kdl` 仍需要按显示器情况调整。

运行这些配置需要预先安装相应程序，例如 niri、waybar、mako、swaylock、swayidle、swaybg、fuzzel、kitty、fastfetch、Python 3、ImageMagick、wl-clipboard、cliphist、nm-connection-editor、pavucontrol；本仓库不安装软件，也不自动启用服务。
