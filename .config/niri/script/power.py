#!/usr/bin/env python3
"""电源选项：锁屏、挂起、休眠、重启、关机和注销。

在浮动 Kitty 中使用共享 curses 菜单；危险操作通过确认菜单二次确认。
锁屏、挂起和休眠统一走 lock.sh，确保操作前已经锁定会话。
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT.parent))

from lib import kitty, tui

LOCK = SCRIPT.parent.parent / 'lock.sh'
APP_ID = 'niri-power'

ACTIONS = [
    {'id': 'lock', 'name': '锁屏', 'detail': '立即锁定当前会话'},
    {'id': 'suspend', 'name': '挂起', 'detail': '锁屏后进入睡眠，按电源键唤醒'},
    {'id': 'hibernate', 'name': '休眠', 'detail': '锁屏后将会话保存到磁盘'},
    {'id': 'reboot', 'name': '重启', 'detail': '重新启动计算机'},
    {'id': 'poweroff', 'name': '关机', 'detail': '关闭计算机'},
    {'id': 'logout', 'name': '注销', 'detail': '结束当前会话'},
]
DESTRUCTIVE = {'reboot', 'poweroff', 'logout'}


def notify(message):
    if shutil.which('notify-send'):
        subprocess.run(['notify-send', '电源选项', message], check=False)
    else:
        print(message, file=sys.stderr)


def power_states():
    try:
        return set(Path('/sys/power/state').read_text().split())
    except OSError:
        return set()


def reason_unavailable(action, states):
    """返回不可用原因；可用时返回 None。只做只读检查，不执行任何动作。"""
    if action == 'lock':
        if not LOCK.is_file():
            return '未找到 lock.sh'
        if not shutil.which('swaylock'):
            return '未找到 swaylock'
        return None
    if action == 'logout':
        if not shutil.which('niri'):
            return '未找到 niri 命令'
        return None
    if not shutil.which('systemctl'):
        return '未找到 systemctl'
    if action == 'suspend' and states and 'mem' not in states:
        return '当前系统不支持挂起'
    if action == 'hibernate':
        if states and 'disk' not in states:
            return '当前系统未启用休眠'
        try:
            swap = Path('/proc/swaps').read_text().splitlines()[1:]
        except OSError:
            swap = []
        if not swap:
            return '未检测到交换空间，无法休眠'
    return None


def available_actions(states):
    return [action for action in ACTIONS
            if reason_unavailable(action['id'], states) is None]


def choose_action():
    actions = available_actions(power_states())
    result = tui.Menu(
        actions,
        render=lambda action: action['name'],
        search=lambda action: action['name'],
        prompt='电源 ❯ ',
        footer='Enter 执行 · Ctrl+R 刷新 · Esc 退出',
        reload=lambda: available_actions(power_states()),
    ).run()
    if not result:
        return None

    action = result[1]
    if action['id'] in DESTRUCTIVE:
        confirm = [
            {'id': 'cancel', 'name': '取消'},
            {'id': action['id'], 'name': '确认' + action['name']},
        ]
        result = tui.Menu(
            confirm,
            render=lambda item: item['name'],
            search=lambda item: item['name'],
            prompt='确认 ❯ ',
            footer='Enter 确认 · Esc 取消',
        ).run()
        if not result or result[1]['id'] == 'cancel':
            return None
    return action['id']


def perform(action):
    if action in ('lock', 'suspend', 'hibernate'):
        # lock.sh 返回时屏幕已经锁定；再执行挂起/休眠可避免内容泄露。
        subprocess.run(['sh', str(LOCK)], check=True)
    if action == 'suspend':
        subprocess.run(['systemctl', 'suspend'], check=True)
    elif action == 'hibernate':
        subprocess.run(['systemctl', 'hibernate'], check=True)
    elif action == 'reboot':
        subprocess.run(['systemctl', 'reboot'], check=True)
    elif action == 'poweroff':
        subprocess.run(['systemctl', 'poweroff'], check=True)
    elif action == 'logout':
        subprocess.run(['niri', 'msg', 'action', 'quit', '--skip-confirmation'],
                       check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--show', action='store_true', help='在当前 Kitty 中显示菜单')
    mode.add_argument('--list', action='store_true', help='只列出电源操作')
    args = parser.parse_args()
    if args.list:
        states = power_states()
        for action in ACTIONS:
            reason = reason_unavailable(action['id'], states)
            print(f'{action["name"]:<8} {reason or action["detail"]}')
    elif args.show:
        action = choose_action()
        if action is not None:
            try:
                perform(action)
            except (OSError, subprocess.CalledProcessError) as error:
                notify(f'操作失败：{error}')
                sys.exit(1)
    else:
        kitty.launch(APP_ID, '电源选项', SCRIPT, ['--show'],
                     width=80, height=24, font_size=11)


if __name__ == '__main__':
    main()
