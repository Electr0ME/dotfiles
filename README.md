# Niri dotfiles

本仓库保存当前 Niri 桌面相关配置的快照，按用户主目录的结构组织。

## 备份内容

- `.config/niri/`：主配置、显示器配置、窗口规则、快捷键、会话/锁屏/空闲脚本、辅助脚本和默认壁纸。
- `.config/waybar/`：状态栏配置与样式。
- `.config/swaync/`：通知中心配置与样式。
- `.config/swaylock/`：锁屏配置。
- `.config/fuzzel/`：应用启动器配置。
- `.config/kitty/`：终端配置与 Catppuccin Mocha 主题（不包含历史 `.bak-*` 文件）。
- `.config/systemd/user/niri-clipboard.service`：Niri 会话剪贴板服务。

不包含历史 `backups/`、Python 缓存、运行日志或剪贴板历史。原有配置未作修改。

## 恢复

先备份目标机器现有配置，再在仓库根目录执行（将覆盖同名文件）：

```sh
mkdir -p "$HOME/.config"
cp -a .config/. "$HOME/.config/"
systemctl --user daemon-reload
```

配置保留了原始 `/home/aoba` 绝对路径；在其他用户下使用时，需要调整 Niri 配置及脚本中的路径。`outputs.kdl` 也需要按显示器情况调整。

运行这些配置需要预先安装相应程序，例如 niri、waybar、swaync、swaylock、swayidle、swaybg、fuzzel、kitty、Python 3、wl-clipboard 和 cliphist；本仓库不安装软件，也不自动启用服务。
