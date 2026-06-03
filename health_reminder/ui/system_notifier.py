# -*- coding: utf-8 -*-
"""Windows 系统原生通知，支持按钮回调。"""
from __future__ import annotations

import threading
from typing import Callable

from windows_toasts import (
    InteractableWindowsToaster,
    Toast,
    ToastActivatedEventArgs,
    ToastButton,
    ToastDuration,
)

from ..services.reminders import ReminderEvent

_toaster = InteractableWindowsToaster("健康提醒助手")


def _show_toast(title: str, message: str,
                buttons: list[ToastButton] | None = None,
                on_activated: Callable[[str], None] | None = None,
                duration: ToastDuration = ToastDuration.Default) -> None:
    """在后台线程发送系统通知。"""
    def _activated_handler(args: ToastActivatedEventArgs) -> None:
        if on_activated and args.arguments:
            on_activated(args.arguments)

    toast = Toast(
        text_fields=[title, message],
        duration=duration,
        on_activated=_activated_handler if on_activated else None,
        actions=buttons or [],
    )
    _toaster.show_toast(toast)


def show_reminder_notification(
    event: ReminderEvent,
    on_water: Callable[[int], None] | None = None,
    on_snooze: Callable[[], None] | None = None,
) -> None:
    """通过系统通知显示提醒，按钮可直接触发操作。"""
    buttons: list[ToastButton] = []
    on_activated: Callable[[str], None] | None = None

    if event.kind in ("water", "combined"):
        buttons = [
            ToastButton("💧 250ml", "water_250"),
            ToastButton("💧 500ml", "water_500"),
            ToastButton("⏰ 稍后", "snooze"),
        ]
        def _handle(action: str) -> None:
            if action == "water_250" and on_water:
                on_water(250)
            elif action == "water_500" and on_water:
                on_water(500)
            elif action == "snooze" and on_snooze:
                on_snooze()
        on_activated = _handle
    elif event.kind == "sedentary":
        buttons = [
            ToastButton("✅ 我起来了", "stand_ok"),
            ToastButton("⏰ 稍后", "snooze"),
        ]
        def _handle(action: str) -> None:
            if action == "snooze" and on_snooze:
                on_snooze()
        on_activated = _handle

    thread = threading.Thread(
        target=_show_toast,
        args=(event.title, event.message),
        kwargs={
            "buttons": buttons,
            "on_activated": on_activated,
            "duration": ToastDuration.Long,
        },
        daemon=True,
    )
    thread.start()


def show_away_reason_notification(
    on_select: Callable[[str], None],
) -> None:
    """通过系统通知选择离席原因，按钮可直接触发。"""
    buttons = [
        ToastButton("🚽 上厕所", "上厕所"),
        ToastButton("🚬 抽根烟", "抽根烟"),
        ToastButton("🏃 蒙多想去哪就去哪", "蒙多想去哪就去哪"),
    ]

    def _handle(action: str) -> None:
        if action:
            on_select(action)

    thread = threading.Thread(
        target=_show_toast,
        args=("欢迎回来", "选择离席原因，会记入今日健康数据"),
        kwargs={
            "buttons": buttons,
            "on_activated": _handle,
            "duration": ToastDuration.Long,
        },
        daemon=True,
    )
    thread.start()