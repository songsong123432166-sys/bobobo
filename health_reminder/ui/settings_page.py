"""设置页面模块，从主界面拆分而来。"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk
from . import scaling

from ..core.config import ConfigStore
from ..core.event_log import EventLogger
from ..platform import autostart


BG = "#f3f4f6"
TEXT = "#20242a"
MUTED = "#6b7280"
LINE = "#e5e7eb"
BLUE = "#2f80ed"
GREEN = "#34a853"
RED = "#ff6b5f"
YELLOW = "#fbbc04"

class SettingsPageMixin:
    """设置页面 Mixin，提供设置页面的构建和交互方法。"""


    def _build_settings(self, parent: tk.Frame) -> None:
        self._header(parent, "设置", "分组调整工作时间、提醒、勿扰、检测和系统行为。")
        config = self.config_store.load()
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self._settings_group(wrap, "工作时间", [("上班时间", "work_time.start", config["work_time"]["start"]), ("下班时间",
            "work_time.end", config["work_time"]["end"])])
        self._settings_group(
            wrap,
            "提醒设置",
            [
                ("久坐间隔（分钟）", "reminders.sedentary_interval_minutes", config["reminders"]["sedentary_interval_minutes"]),
                ("喝水间隔（分钟）", "reminders.water_interval_minutes", config["reminders"]["water_interval_minutes"]),
                ("喝水稍后提醒（分钟）", "reminders.water_snooze_minutes", config["reminders"]["water_snooze_minutes"]),
                ("合并提醒窗口（分钟）", "reminders.merge_window_minutes", config["reminders"]["merge_window_minutes"]),
            ],
        )
        self._settings_group(
            wrap,
            "勿扰设置",
            [
                ("是否启用", "do_not_disturb.enabled", config["do_not_disturb"]["enabled"]),
                ("开始时间", "do_not_disturb.start", config["do_not_disturb"]["start"]),
                ("结束时间", "do_not_disturb.end", config["do_not_disturb"]["end"]),
            ],
        )
        self._settings_group(
            wrap,
            "状态检测",
            [
                ("离开判断时间（秒）", "detection.away_after_seconds", config["detection"]["away_after_seconds"]),
                ("空闲判断时间（秒）", "detection.idle_after_seconds", config["detection"]["idle_after_seconds"]),
                ("摄像头触发空闲时间（秒）", "detection.camera_idle_threshold_seconds",
                    config["detection"]["camera_idle_threshold_seconds"]),
                ("摄像头检测间隔（秒）", "detection.camera_interval_seconds", config["detection"]["camera_interval_seconds"]),
                ("无人后摄像头检测间隔（秒）", "detection.camera_away_interval_seconds",
                    config["detection"]["camera_away_interval_seconds"]),
                ("离席红灯阈值（秒）", "detection.away_red_after_seconds", config["detection"]["away_red_after_seconds"]),
                ("站起检测间隔（秒）", "detection.stand_watch_interval_seconds",
                    config["detection"]["stand_watch_interval_seconds"]),
                ("站起检测持续时间（秒）", "detection.stand_watch_duration_seconds",
                    config["detection"]["stand_watch_duration_seconds"]),
                ("摄像头检测", "detection.camera_enabled", config["detection"]["camera_enabled"]),
                ("隐私模式（暂停摄像头）", "detection.privacy_mode", config["detection"]["privacy_mode"]),
                ("中央弹窗", "detection.center_popup_enabled", config["detection"]["center_popup_enabled"]),
            ],
        )
        self._privacy_note(wrap)
        self._settings_group(
            wrap,
            "今日目标",
            [
                ("喝水目标（ml）", "goals.water_ml", config["goals"]["water_ml"]),
                ("起身目标（次）", "goals.stand_count", config["goals"]["stand_count"]),
                ("最长久坐目标（分钟）", "goals.max_sit_streak_minutes", config["goals"]["max_sit_streak_minutes"]),
            ],
        )
        self._settings_group(
            wrap,
            "系统设置",
            [
                ("开机自启", "system.autostart", autostart.is_enabled()),
                ("提示音音量（0-100）", "system.sound_volume_percent", config["system"]["sound_volume_percent"]),
            ],
        )
        self._preset_tools(wrap)
        self._test_tools(wrap)
        ttk.Button(wrap, text="保存设置", command=self._save_settings).pack(anchor="e", pady=(0, 18), padx=2)
        self._settings_log(wrap)

    def _settings_group(self, parent: tk.Frame, title: str, rows: list[tuple[str, str, Any]]) -> None:
        card = self._card(parent, title)
        card.pack(fill="x", pady=(0, 14))
        for label, key, value in rows:
            row = tk.Frame(card, bg="white")
            row.pack(fill="x", padx=18, pady=7)
            tk.Label(row, text=label, bg="white", fg=TEXT, font=scaling.font("Microsoft YaHei UI", 10)).pack(side="left")
            if isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                ttk.Checkbutton(row, variable=var).pack(side="right")
            else:
                var = tk.StringVar(value=str(value))
                ttk.Entry(row, textvariable=var, width=18).pack(side="right")
            self.setting_vars[key] = var

    def _privacy_note(self, parent: tk.Frame) -> None:
        card = self._card(parent, "隐私说明")
        card.pack(fill="x", pady=(0, 14))
        tk.Label(
            card,
            text="摄像头只在键鼠空闲后短暂检测是否有人，不保存画面，也不会上传画面。开启隐私模式后，程序不会调用摄像头。",
            bg="white",
            fg=MUTED,
            font=scaling.font("Microsoft YaHei UI", 10),
            wraplength=720,
            justify="left",
        ).pack(fill="x", padx=18, pady=(0, 16))

    def _preset_tools(self, parent: tk.Frame) -> None:
        card = self._card(parent, "模式预设")
        card.pack(fill="x", pady=(0, 14))
        row = tk.Frame(card, bg="white")
        row.pack(fill="x", padx=18, pady=(0, 16))
        presets = [
            ("推荐模式", {
                "reminders.sedentary_interval_minutes": "45",
                "reminders.water_interval_minutes": "60",
                "detection.camera_enabled": True,
                "detection.privacy_mode": False,
                "detection.camera_idle_threshold_seconds": "20",
                "detection.camera_interval_seconds": "15",
                "detection.camera_away_interval_seconds": "60",
                "detection.center_popup_enabled": True,
            }),
            ("轻量模式", {
                "reminders.sedentary_interval_minutes": "60",
                "reminders.water_interval_minutes": "90",
                "detection.camera_enabled": False,
                "detection.privacy_mode": True,
                "detection.camera_idle_threshold_seconds": "60",
                "detection.camera_interval_seconds": "60",
                "detection.center_popup_enabled": False,
            }),
            ("隐私模式", {
                "detection.camera_enabled": False,
                "detection.privacy_mode": True,
                "detection.center_popup_enabled": False,
            }),
        ]
        for text, values in presets:
            ttk.Button(row, text=text, command=lambda item=values: self._apply_preset(item)).pack(side="left", padx=(0,
                8))

    def _apply_preset(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            var = self.setting_vars.get(key)
            if var is not None:
                var.set(value)
        messagebox.showinfo("模式已套用", "预设已填入，点击保存设置后生效。")

    def _test_tools(self, parent: tk.Frame) -> None:
        card = self._card(parent, "测试工具")
        card.pack(fill="x", pady=(0, 14))
        row = tk.Frame(card, bg="white")
        row.pack(fill="x", padx=18, pady=(0, 16))
        ttk.Button(row, text="测试提示音", command=self.on_test_sound).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="测试右下角弹窗", command=self.on_test_popup).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="测试中央弹窗", command=self.on_test_center_popup).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="测试摄像头", command=self._show_camera_diagnostic).pack(side="left")

    def _show_camera_diagnostic(self) -> None:
        messagebox.showinfo("摄像头检测结果", self.on_test_camera())

    def _settings_log(self, parent: tk.Frame) -> None:
        log_card = self._card(parent, "运行日志")
        log_card.pack(fill="x", pady=(0, 18))
        for line in self.logger.tail(10) or ["暂无日志"]:
            tk.Label(log_card, text=line, bg="white", fg="#4b5563", anchor="w", font=scaling.font("Consolas", 9)).pack(fill="x",
                padx=18, pady=3)

    def _save_settings(self) -> None:
        config = self.config_store.load()
        for key, var in self.setting_vars.items():
            cursor = config
            parts = key.split(".")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            default = cursor.get(parts[-1])
            raw = var.get()
            if isinstance(default, bool):
                value = bool(raw)
            elif isinstance(default, int):
                try:
                    value = int(raw)
                except ValueError:
                    value = default
            else:
                value = str(raw)
            cursor[parts[-1]] = value

        autostart.set_enabled(bool(config.get("system", {}).get("autostart", False)))
        self.config_store.save(config)
        self.on_save_config(config)
        self.logger.log("settings_saved", "user saved settings")
        messagebox.showinfo("设置已保存", "新的提醒设置已经生效。")

