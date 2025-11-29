import asyncio
import random
import sys

from PyQt5 import QtWidgets, QtCore
from pynput import keyboard as pynput_keyboard   # для глобального хоткея
import keyboard as lowlevel_keyboard             # низкоуровневые нажатия (для игр)
from qasync import QEventLoop


# ==========================
#   ЛОГИКА АВТО-НАЖАТИЙ
# ==========================

class AutoPresser(QtCore.QObject):
    state_changed = QtCore.pyqtSignal(bool)  # True = запущено, False = остановлено

    def __init__(self):
        super().__init__()
        self.running = False
        self.task = None

        # Параметры (значения по умолчанию, потом переопределятся из настроек)
        self.sequence = ["w", "a", "s", "d"]
        self.interval = 0.5
        self.random_interval = False
        self.interval_min = 0.3
        self.interval_max = 0.7
        self.shuffle = False
        self.hold_time = 0.05  # сколько сек удерживать клавишу

    async def _run(self):
        """Основной асинхронный цикл."""
        self.state_changed.emit(True)
        try:
            while self.running:
                seq = list(self.sequence)
                if not seq:
                    break

                # случайный порядок клавиш
                if self.shuffle:
                    random.shuffle(seq)

                for ch in seq:
                    if not self.running:
                        break

                    # Нажатие и удержание
                    try:
                        lowlevel_keyboard.press(ch)
                        await asyncio.sleep(self.hold_time)
                        lowlevel_keyboard.release(ch)
                    except Exception:
                        # Если клавишу не получилось отправить — пропускаем
                        pass

                    if not self.running:
                        break

                    # Выбор интервала
                    if self.random_interval:
                        delay = random.uniform(self.interval_min, self.interval_max)
                    else:
                        delay = self.interval

                    await asyncio.sleep(max(0.0, delay))
        finally:
            self.running = False
            self.task = None
            self.state_changed.emit(False)

    def start(self):
        if self.running or not self.sequence:
            return
        self.running = True
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self._run())

    def stop(self):
        self.running = False
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()


# ==========================
#   ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================

def key_to_name(k):
    """Переводит pynput-клавишу в строку: 'a', 'f8', 'space' и т.д."""
    try:
        if isinstance(k, pynput_keyboard.KeyCode) and k.char is not None:
            return k.char.lower()
        if isinstance(k, pynput_keyboard.Key):
            return str(k).split('.')[-1].lower()
    except Exception:
        pass
    return ""


def parse_sequence(text: str):
    """
    Преобразует строку в список клавиш.
    Сейчас просто посимвольно: 'wasd' -> ['w', 'a', 's', 'd'].
    """
    text = text.strip()
    if not text:
        return []
    return list(text)


# ==========================
#   ОКНО НАСТРОЕК
# ==========================

class SettingsDialog(QtWidgets.QDialog):
    """
    Окно "Настройки":
      - клавиши
      - базовый интервал + рандомный диапазон
      - удержание
      - shuffle
      - горячая клавиша
      - always on top
      - тема
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setFixedSize(360, 320)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)

        # Последовательность клавиш
        self.seq_edit = QtWidgets.QLineEdit()
        form.addRow("Клавиши по кругу:", self.seq_edit)

        # Базовый интервал
        self.interval_spin = QtWidgets.QDoubleSpinBox()
        self.interval_spin.setRange(0.01, 10.0)
        self.interval_spin.setSingleStep(0.05)
        form.addRow("Базовый интервал (сек):", self.interval_spin)

        # Случайный интервал
        self.random_check = QtWidgets.QCheckBox("Случайный интервал")
        form.addRow("", self.random_check)

        # Диапазон рандома
        self.min_spin = QtWidgets.QDoubleSpinBox()
        self.min_spin.setRange(0.01, 10.0)
        self.min_spin.setSingleStep(0.05)

        self.max_spin = QtWidgets.QDoubleSpinBox()
        self.max_spin.setRange(0.01, 10.0)
        self.max_spin.setSingleStep(0.05)

        range_layout = QtWidgets.QHBoxLayout()
        range_layout.addWidget(QtWidgets.QLabel("от"))
        range_layout.addWidget(self.min_spin)
        range_layout.addWidget(QtWidgets.QLabel("до"))
        range_layout.addWidget(self.max_spin)
        form.addRow("Диапазон интервала:", range_layout)

        # Время удержания
        self.hold_spin = QtWidgets.QDoubleSpinBox()
        self.hold_spin.setRange(0.01, 2.0)
        self.hold_spin.setSingleStep(0.01)
        form.addRow("Время удержания (сек):", self.hold_spin)

        # Случайный порядок
        self.shuffle_check = QtWidgets.QCheckBox("Случайный порядок клавиш")
        form.addRow("", self.shuffle_check)

        # Горячая клавиша
        self.hotkey_edit = QtWidgets.QLineEdit()
        form.addRow("Горячая клавиша Start/Stop:", self.hotkey_edit)

        # Always on top
        self.on_top_check = QtWidgets.QCheckBox("Всегда поверх окон")
        form.addRow("", self.on_top_check)

        # Тема
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Neon"])
        form.addRow("Тема оформления:", self.theme_combo)

        layout.addLayout(form)

        # Кнопки ОК / Отмена
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)


# ==========================
#   ГЛАВНОЕ ОКНО
# ==========================

class MainWindow(QtWidgets.QMainWindow):
    hotkeyTriggered = QtCore.pyqtSignal()  # сигнал от глобальной клавиши

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Key Auto Presser")
        self.setFixedSize(320, 210)

        # QSettings для сохранения настроек
        self.settings = QtCore.QSettings("TimApp", "KeyAutoPresser")

        # Логика автопресса
        self.worker = AutoPresser()
        self.worker.state_changed.connect(self.on_worker_state_changed)

        self.app_running = True
        self.global_hotkey_name = "f8"
        self.current_theme = "Dark"
        self.on_top_enabled = True
        self.really_quit = False

        # UI
        self._build_ui()
        self._create_menus()
        self._create_tray_icon()

        # Загрузка настроек и применение темы
        self._load_settings()
        self._apply_theme(self.current_theme)

        # Глобальный слушатель клавиатуры (только для хоткея)
        self.listener = pynput_keyboard.Listener(on_press=self.on_hotkey_press)
        self.listener.start()

        # Соединяем сигнал от хоткея с логикой
        self.hotkeyTriggered.connect(self.toggle_start_stop)

        # Анимация индикатора
        self.blink_timer = QtCore.QTimer(self)
        self.blink_timer.setInterval(300)
        self.blink_timer.timeout.connect(self._update_indicator_animation)
        self.blink_state = False
        self.blink_timer.start()

        self._center_on_screen()

    # ---------- Построение UI ----------

    def _center_on_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            self.move(
                rect.center().x() - self.width() // 2,
                rect.center().y() - self.height() // 2,
            )

    def _build_ui(self):
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # Заголовок
        self.title = QtWidgets.QLabel("Key Auto Presser")
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        self.title.setObjectName("TitleLabel")
        main_layout.addWidget(self.title)

        # Индикатор состояния
        self.indicator = QtWidgets.QLabel("Остановлено")
        self.indicator.setAlignment(QtCore.Qt.AlignCenter)
        self.indicator.setObjectName("IndicatorLabel")
        main_layout.addWidget(self.indicator)

        # Кнопки
        btn_layout = QtWidgets.QHBoxLayout()

        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.clicked.connect(self.toggle_start_stop)
        btn_layout.addWidget(self.start_btn)

        self.settings_btn = QtWidgets.QPushButton("Настройки…")
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        btn_layout.addWidget(self.settings_btn)

        self.to_tray_btn = QtWidgets.QPushButton("В трей")
        self.to_tray_btn.clicked.connect(self.hide_to_tray)
        btn_layout.addWidget(self.to_tray_btn)

        main_layout.addLayout(btn_layout)



    def _create_menus(self):
        bar = self.menuBar()
        settings_menu = bar.addMenu("Настройки")

        open_settings = settings_menu.addAction("Открыть настройки…")
        open_settings.triggered.connect(self.open_settings_dialog)

        quit_action = settings_menu.addAction("Выход")
        quit_action.triggered.connect(self.quit_app)

    def _create_tray_icon(self):
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)

        tray_menu = QtWidgets.QMenu()
        show_action = tray_menu.addAction("Открыть окно")
        show_action.triggered.connect(self.show_from_tray)

        start_stop_action = tray_menu.addAction("Start/Stop")
        start_stop_action.triggered.connect(self.toggle_start_stop)

        quit_action = tray_menu.addAction("Выход")
        quit_action.triggered.connect(self.quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    # ---------- Темы ----------

    def _theme_styles(self, name):
        if name == "Light":
            return """
                QMainWindow { background-color: #f3f3f3; }
                #TitleLabel { font-size: 18px; font-weight: 600; color: #222; }
                QLabel { color: #333; }
                #HintLabel { color: #666; font-size: 11px; }
                QPushButton {
                    background-color: #4f8cff;
                    color: #ffffff;
                    border-radius: 8px;
                    padding: 6px 10px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: #5f9cff; }
                QPushButton:pressed { background-color: #3f7ce0; }
                #IndicatorLabel { font-size: 14px; font-weight: 600; }
            """
        if name == "Neon":
            return """
                QMainWindow { background-color: #050816; }
                #TitleLabel { font-size: 18px; font-weight: 600; color: #00eaff; }
                QLabel { color: #e0e0ff; }
                #HintLabel { color: #7788ff; font-size: 11px; }
                QPushButton {
                    background-color: #8a2be2;
                    color: #ffffff;
                    border-radius: 8px;
                    padding: 6px 10px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: #9d3fff; }
                QPushButton:pressed { background-color: #6c1fb3; }
                #IndicatorLabel { font-size: 14px; font-weight: 600; color: #00ff99; }
            """
        # Dark (по умолчанию)
        return """
            QMainWindow { background-color: #1f2428; }
            #TitleLabel { font-size: 18px; font-weight: 600; color: #f5f5f5; }
            QLabel { color: #d0d0d0; }
            #HintLabel { color: #888888; font-size: 11px; }
            QPushButton {
                background-color: #2d8cff;
                color: #ffffff;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #3d9cff; }
            QPushButton:pressed { background-color: #1c6ad8; }
            #IndicatorLabel { font-size: 14px; font-weight: 600; }
        """

    def _apply_theme(self, name):
        self.setStyleSheet(self._theme_styles(name))

    # ---------- Настройки ----------

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)

        # Заполняем текущими значениями
        seq_string = "".join(self.worker.sequence) if self.worker.sequence else "wasd"
        dlg.seq_edit.setText(seq_string)
        dlg.interval_spin.setValue(self.worker.interval)
        dlg.random_check.setChecked(self.worker.random_interval)
        dlg.min_spin.setValue(self.worker.interval_min)
        dlg.max_spin.setValue(self.worker.interval_max)
        dlg.hold_spin.setValue(self.worker.hold_time)
        dlg.shuffle_check.setChecked(self.worker.shuffle)
        dlg.hotkey_edit.setText(self.global_hotkey_name)
        dlg.on_top_check.setChecked(self.on_top_enabled)
        dlg.theme_combo.setCurrentText(self.current_theme)

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            # Забираем значения обратно
            self.worker.sequence = parse_sequence(dlg.seq_edit.text())
            self.worker.interval = dlg.interval_spin.value()
            self.worker.random_interval = dlg.random_check.isChecked()
            self.worker.interval_min = min(dlg.min_spin.value(), dlg.max_spin.value())
            self.worker.interval_max = max(dlg.min_spin.value(), dlg.max_spin.value())
            self.worker.hold_time = dlg.hold_spin.value()
            self.worker.shuffle = dlg.shuffle_check.isChecked()
            self.global_hotkey_name = dlg.hotkey_edit.text().strip().lower() or "f8"
            self.on_top_enabled = dlg.on_top_check.isChecked()
            self.current_theme = dlg.theme_combo.currentText()

            # Применяем флаг always on top
            self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, self.on_top_enabled)
            self.show()  # нужно пересоздать окно

            self._apply_theme(self.current_theme)
            self._save_settings()

    # ---------- Трей ----------

    def hide_to_tray(self):
        self.hide()
        self.tray_icon.showMessage(
            "Key Auto Presser",
            "Приложение свернуто в трей.",
            QtWidgets.QSystemTrayIcon.Information,
            2000,
        )

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:  # ЛКМ
            if self.isHidden():
                self.show_from_tray()
            else:
                self.hide_to_tray()

    # ---------- Управление запуском ----------

    def toggle_start_stop(self):
        if not self.worker.sequence:
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                "Последовательность клавиш не задана.\nОткрой «Настройки» и задай её.",
            )
            return
        self.worker.toggle()

    def on_worker_state_changed(self, is_running: bool):
        if is_running:
            self.start_btn.setText("Stop")
        else:
            self.start_btn.setText("Start")
            self.blink_state = False
        self._update_indicator_text(is_running)

    def _update_indicator_text(self, is_running: bool):
        if is_running:
            self.indicator.setText("Работает")
        else:
            self.indicator.setText("Остановлено")

    def _update_indicator_animation(self):
        if self.worker.running:
            self.blink_state = not self.blink_state
            dot = "●" if self.blink_state else "○"
            self.indicator.setText(f"Работает {dot}")
        else:
            if self.indicator.text() != "Остановлено":
                self.indicator.setText("Остановлено")

    # ---------- Глобальный хоткей ----------

    def on_hotkey_press(self, key):
        if not self.app_running:
            return False

        name = key_to_name(key)
        hotkey_str = (self.global_hotkey_name or "f8").lower()

        if name == hotkey_str:
            self.hotkeyTriggered.emit()

    # ---------- Закрытие и сохранение ----------

    def closeEvent(self, event):
        if not self.really_quit:
            event.ignore()
            self.hide_to_tray()
        else:
            self.app_running = False
            try:
                self.listener.stop()
            except Exception:
                pass
            self._save_settings()
            event.accept()

    def quit_app(self):
        self.really_quit = True
        self.tray_icon.hide()
        QtWidgets.QApplication.quit()

    # ---------- QSettings ----------

    def _load_settings(self):
        # базовые
        sequence_str = self.settings.value("sequence", "wasd")
        self.worker.sequence = parse_sequence(sequence_str)

        self.worker.interval = float(self.settings.value("interval", 0.5))
        self.global_hotkey_name = self.settings.value("hotkey", "f8").lower()

        self.on_top_enabled = self.settings.value("on_top", "true") == "true"
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, self.on_top_enabled)

        self.current_theme = self.settings.value("theme", "Dark")

        # продвинутые
        self.worker.random_interval = (
            self.settings.value("random_interval", "false") == "true"
        )
        self.worker.interval_min = float(self.settings.value("interval_min", 0.3))
        self.worker.interval_max = float(self.settings.value("interval_max", 0.7))
        self.worker.hold_time = float(self.settings.value("hold_time", 0.05))
        self.worker.shuffle = self.settings.value("shuffle", "false") == "true"

    def _save_settings(self):
        seq_str = "".join(self.worker.sequence)
        self.settings.setValue("sequence", seq_str)
        self.settings.setValue("interval", self.worker.interval)
        self.settings.setValue("hotkey", self.global_hotkey_name)
        self.settings.setValue(
            "on_top", "true" if self.on_top_enabled else "false"
        )
        self.settings.setValue("theme", self.current_theme)

        self.settings.setValue(
            "random_interval", "true" if self.worker.random_interval else "false"
        )
        self.settings.setValue("interval_min", self.worker.interval_min)
        self.settings.setValue("interval_max", self.worker.interval_max)
        self.settings.setValue("hold_time", self.worker.hold_time)
        self.settings.setValue(
            "shuffle", "true" if self.worker.shuffle else "false"
        )


# ==========================
#   ТОЧКА ВХОДА
# ==========================

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Подключаем asyncio к Qt через qasync
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
