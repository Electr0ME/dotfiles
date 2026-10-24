# Niri 脚本与快捷键窗口

## 脚本启动器（Super+X）

`script-launcher.py` 打开居中浮动的 80×24 Kitty 脚本菜单。
菜单由同目录下的 `menu.json` 手动维护，不再扫描目录，按配置顺序显示。

```json
[
  {"name": "快捷键帮助", "script": "keybindings.py", "args": []}
]
```

- `name`：菜单显示名称，可以使用中文。
- `script`：脚本路径；相对路径以 menu.json 所在目录为基准，也支持绝对路径或 `~/`。
- `args`：可选参数数组，省略时为空；每个参数单独一个字符串，不经 shell 解析。
- 仅加入配置的项目会显示。新增文件不会自动出现在菜单中。
- 直接输入实时搜索显示名称，`↑/↓` 选择，Enter 执行。
- `PgUp/PgDn` 翻页，`Ctrl+U` 清空搜索，`Ctrl+R` 刷新列表，Esc 关闭。
- 按 Enter 后脚本在后台独立运行，菜单窗口立即关闭；工作目录为 `~/.config/niri/script/`。
- 输出追加到 `~/.local/state/niri/script-launcher.log`（遵循 `XDG_STATE_HOME`）。
- 后台脚本不能从菜单终端读取输入；需要交互的脚本应自行打开终端窗口。
- 启动失败时显示错误，按 Enter 返回菜单。
- 可执行脚本沿用 shebang；不可执行脚本按扩展名选择解释器。
- `./script-launcher.py --list` 可检查菜单条目。

## 切换壁纸

菜单中的“切换壁纸”运行 `wallpaper.py`，打开居中浮动的 80×24 Kitty。
左侧实时搜索和选择 `~/Pictures/Wallpapers/` 中的图片（包含子目录），
右侧通过 `kitten icat` 使用 Kitty graphics protocol 显示图片预览。
图片异步解码，不占用键盘输入；切换选中项时更新预览。
直接输入搜索，↑↓ 选择，PgUp/PgDn 翻页，Ctrl+U 清空，Enter 应用并关闭，Esc 取消。
预览不能解码时会显示提示，不阻止选择。使用 swaybg 的 fill 模式应用壁纸。
选择保存到 `~/.local/state/niri/wallpaper`（遵循 XDG_STATE_HOME），
下次登录由 `session-start.sh` 恢复；文件不存在时回退到默认 Mocha 壁纸。
`./wallpaper.py --list` 仅列出图片，不改变当前壁纸。

## 快捷键窗口（Super+Shift+/）

`keybindings.py` 使用独立 app-id `niri-keybindings` 启动居中的浮动 Kitty。
入口绑定在 `../binds.kdl` 的 `Mod+Shift+Slash`。

## 界面

80 列 × 24 行，仅包含搜索输入框、分割线和快捷键列表。
打开即可输入，按键组合与中文说明实时过滤；空格分隔的多个词需全部匹配。
不显示额外的标题、操作说明或状态栏。

## 操作

- 直接输入：实时搜索，无须先按 `/` 或 Enter。
- `↑/↓`：滚动；`PgUp/PgDn`：翻页。
- `←/→`、`Home/End`：移动搜索输入光标。
- Backspace / Delete：删除输入；`Ctrl+U`：清空搜索。
- `Ctrl+R`：重新读取快捷键配置。
- Esc / `Ctrl+C`：关闭窗口，不显示 Kitty 关闭确认。
- `q`、`j`、`k` 等普通字符用于搜索，不再是退出或滚动快捷键。

```sh
~/.config/niri/script/keybindings.py         # 打开窗口，已打开时聚焦
~/.config/niri/script/keybindings.py --list  # 输出纯文本，用于检查
```

列表动态读取 `../binds.kdl`，支持目前使用的每条绑定占一行的写法。
优先显示 `hotkey-overlay-title="说明"`，否则翻译已知动作；未知动作显示原始命令。

行列数在脚本启动 Kitty 的 `initial_window_width=80c` 与
`initial_window_height=24c` 中设置。Niri 规则不强制像素尺寸，保留默认居中行为。
窗口沿用 Kitty 的 Mocha 主题，单独设为不透明、禁用关闭确认，不影响普通 Kitty。
依赖 Python 标准库（含 curses）、Kitty 和 Niri，无额外 Python 包。
