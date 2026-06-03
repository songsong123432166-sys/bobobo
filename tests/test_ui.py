"""UI组件测试，覆盖页面切换、数据刷新和评分显示。"""
from __future__ import annotations

import tkinter as tk
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from health_reminder.core.config import ConfigStore
from health_reminder.core.event_log import EventLogger
from health_reminder.core.health_state import HealthStateStore
from health_reminder.core.paths import DataPaths


class MainWindowTest(unittest.TestCase):
    """主界面测试，验证页面切换和数据展示逻辑。"""

    @classmethod
    def setUpClass(cls):
        """创建共享的tkinter根窗口。"""
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        """销毁根窗口。"""
        try:
            cls.root.destroy()
        except tk.TclError:
            pass

    def setUp(self):
        """为每个测试创建临时目录和主窗口实例。"""
        self._temp = TemporaryDirectory()
        self.paths = DataPaths(Path(self._temp.name))
        self.config_store = ConfigStore(self.paths)
        self.logger = EventLogger(self.paths.log)
        self.state = HealthStateStore(
            self.paths.health_score, self.paths.away_reason
        )
        self.get_remaining = lambda: (600, 1200)
        self.on_save = lambda cfg: None

        from health_reminder.ui.main_window import MainWindow
        self.win = MainWindow(
            self.root,
            self.config_store,
            self.state,
            self.logger,
            self.get_remaining,
            self.on_save,
            on_test_sound=lambda: None,
            on_test_camera=lambda: "ok",
            on_test_popup=lambda: None,
            on_test_center_popup=lambda: None,
        )

    def tearDown(self):
        """关闭窗口并清理临时目录。"""
        try:
            self.win.hide()
        except Exception:
            pass
        self._temp.cleanup()

    def test_show_creates_window(self):
        """show() 后窗口存在且可见。"""
        self.win.show()
        self.root.update()
        self.assertIsNotNone(self.win.window)
        self.assertTrue(self.win.window.winfo_exists())

    def test_default_page_is_visual(self):
        """默认页面应为可视化数据。"""
        self.win.show()
        self.root.update()
        self.assertEqual(self.win.page, "visual")

    def test_switch_to_calendar(self):
        """切换到日历页面后page属性更新。"""
        self.win.show()
        self.root.update()
        self.win._switch("calendar")
        self.root.update()
        self.assertEqual(self.win.page, "calendar")

    def test_switch_to_settings(self):
        """切换到设置页面后page属性更新。"""
        self.win.show()
        self.root.update()
        self.win._switch("settings")
        self.root.update()
        self.assertEqual(self.win.page, "settings")

    def test_switch_same_page_noop(self):
        """重复切换同一页面不应触发重建。"""
        self.win.show()
        self.root.update()
        old_page = self.win.page
        self.win._switch(old_page)
        self.assertEqual(self.win.page, old_page)

    def test_visual_labels_populated(self):
        """可视化页面应创建数据标签。"""
        self.win.show()
        self.root.update()
        self.assertIn("sedentary_seconds", self.win._visual_labels)
        self.assertIn("water_count", self.win._visual_labels)
        self.assertIn("stand_count", self.win._visual_labels)

    def test_update_visual_values_sets_text(self):
        """刷新后标签文本应为非空字符串。"""
        self.win.show()
        self.root.update()
        self.win._update_visual_values()
        self.root.update()
        label = self.win._visual_labels.get("water_count")
        self.assertIsNotNone(label)
        self.assertTrue(len(label.cget("text")) > 0)

    def test_score_display(self):
        """健康分标签应显示数字。"""
        self.win.show()
        self.root.update()
        self.win._update_visual_values()
        self.root.update()
        if hasattr(self.win, "_score_num_label"):
            text = self.win._score_num_label.cget("text")
            self.assertTrue(text.isdigit() or text == "--")

    def test_hide_withdraws_window(self):
        """hide() 后窗口应被隐藏。"""
        self.win.show()
        self.root.update()
        self.win.hide()
        self.root.update()
        if self.win.window:
            self.assertEqual(self.win.window.state(), "withdrawn")


class ScoreDisplayTest(unittest.TestCase):
    """评分显示测试，验证分数到颜色的映射。"""

    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except tk.TclError:
            pass

    def setUp(self):
        self._temp = TemporaryDirectory()
        self.paths = DataPaths(Path(self._temp.name))
        self.config_store = ConfigStore(self.paths)
        self.logger = EventLogger(self.paths.log)
        self.state = HealthStateStore(
            self.paths.health_score, self.paths.away_reason
        )
        from health_reminder.ui.main_window import MainWindow
        self.win = MainWindow(
            self.root, self.config_store, self.state, self.logger,
            lambda: (600, 1200), lambda cfg: None,
            on_test_sound=lambda: None,
            on_test_camera=lambda: "ok",
            on_test_popup=lambda: None,
            on_test_center_popup=lambda: None,
        )

    def tearDown(self):
        try:
            self.win.hide()
        except Exception:
            pass
        self._temp.cleanup()

    def test_high_score_green(self):
        """80分及以上应显示绿色。"""
        self.win.show()
        self.root.update()
        self.win._draw_score(85)
        if hasattr(self.win, "_score_num_label"):
            color = self.win._score_num_label.cget("fg")
            self.assertEqual(color, "#34a853")

    def test_medium_score_yellow(self):
        """60-79分应显示黄色。"""
        self.win.show()
        self.root.update()
        self.win._draw_score(70)
        if hasattr(self.win, "_score_num_label"):
            color = self.win._score_num_label.cget("fg")
            self.assertEqual(color, "#fbbc04")

    def test_low_score_red(self):
        """60分以下应显示红色。"""
        self.win.show()
        self.root.update()
        self.win._draw_score(40)
        if hasattr(self.win, "_score_num_label"):
            color = self.win._score_num_label.cget("fg")
            self.assertEqual(color, "#ff6b5f")


class OnboardingWizardTest(unittest.TestCase):
    """首次引导向导测试。"""

    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except tk.TclError:
            pass

    def test_detection_mode_card_selection_updates_without_page_rebuild(self):
        from health_reminder.core.config import DEFAULT_CONFIG
        from health_reminder.ui.onboarding import OnboardingWizard

        completed = MagicMock()
        wizard = OnboardingWizard(self.root, DEFAULT_CONFIG.copy(), completed)
        try:
            wizard._page_index = 2
            wizard._render_page()
            self.root.update()
            self.assertEqual(wizard._detection_mode.get(), "recommended")

            wizard._select_detection_mode("privacy")
            self.root.update()

            self.assertEqual(wizard._detection_mode.get(), "privacy")
            self.assertEqual(wizard._mode_indicators["privacy"].cget("text"), "●")
            self.assertEqual(wizard._mode_indicators["recommended"].cget("text"), "○")
            self.assertTrue(wizard._mode_cards["privacy"].winfo_exists())
        finally:
            wizard.destroy()


if __name__ == "__main__":
    unittest.main()
