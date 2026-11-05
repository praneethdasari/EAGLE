"""Settings and preferences dialog for EAGLE configuration management."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from eagle.core.config import EagleConfig, save_config


class SettingsDialog(QDialog):
    """Modal configuration dialog allowing user customization across all EAGLE subsystems."""

    settings_saved = Signal(object)  # Emits updated EagleConfig

    def __init__(
        self,
        config: EagleConfig,
        config_path: Path | str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.config_path = config_path
        self.setWindowTitle("EAGLE — Settings & Preferences")
        self.resize(680, 560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Tab Widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._init_voice_tab()
        self._init_ai_tab()
        self._init_security_tab()
        self._init_ui_tab()

        # Dialog Buttons (Save / Cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("Save Preferences")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(self._save_btn)

        layout.addLayout(btn_layout)

    def _init_voice_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # Wake word group
        ww_group = QGroupBox("Wake-Word Detection")
        ww_layout = QFormLayout(ww_group)
        ww_layout.setSpacing(10)

        self._ww_enabled = QCheckBox("Enable Continuous Wake-Word Detection")
        self._ww_enabled.setChecked(self.config.audio.wake_word_enabled)
        ww_layout.addRow(self._ww_enabled)

        self._ww_phrase = QLineEdit(self.config.audio.wake_word_phrase)
        ww_layout.addRow("Wake Phrase:", self._ww_phrase)

        self._ww_engine = QComboBox()
        self._ww_engine.addItems(["local_stt", "openwakeword", "mock"])
        idx = self._ww_engine.findText(self.config.audio.wake_word_engine)
        if idx >= 0:
            self._ww_engine.setCurrentIndex(idx)
        ww_layout.addRow("Wake Engine:", self._ww_engine)

        self._ww_sens = QSlider(Qt.Orientation.Horizontal)
        self._ww_sens.setRange(10, 95)
        self._ww_sens.setValue(int(self.config.audio.wake_word_sensitivity * 100))
        self._ww_sens_val = QLabel(f"{self.config.audio.wake_word_sensitivity:.2f}")
        self._ww_sens.valueChanged.connect(lambda v: self._ww_sens_val.setText(f"{v / 100.0:.2f}"))
        sens_row = QHBoxLayout()
        sens_row.addWidget(self._ww_sens)
        sens_row.addWidget(self._ww_sens_val)
        ww_layout.addRow("Sensitivity:", sens_row)

        layout.addWidget(ww_group)

        # TTS & Audio synthesis group
        tts_group = QGroupBox("Voice Output & Synthesis (TTS)")
        tts_layout = QFormLayout(tts_group)
        tts_layout.setSpacing(10)

        self._tts_rate = QSlider(Qt.Orientation.Horizontal)
        self._tts_rate.setRange(100, 300)
        self._tts_rate.setValue(self.config.audio.tts_rate)
        self._tts_rate_val = QLabel(f"{self.config.audio.tts_rate} WPM")
        self._tts_rate.valueChanged.connect(lambda v: self._tts_rate_val.setText(f"{v} WPM"))
        rate_row = QHBoxLayout()
        rate_row.addWidget(self._tts_rate)
        rate_row.addWidget(self._tts_rate_val)
        tts_layout.addRow("Speech Rate:", rate_row)

        self._tts_volume = QSlider(Qt.Orientation.Horizontal)
        self._tts_volume.setRange(10, 100)
        self._tts_volume.setValue(int(self.config.audio.tts_volume * 100))
        self._tts_volume_val = QLabel(f"{int(self.config.audio.tts_volume * 100)}%")
        self._tts_volume.valueChanged.connect(lambda v: self._tts_volume_val.setText(f"{v}%"))
        vol_row = QHBoxLayout()
        vol_row.addWidget(self._tts_volume)
        vol_row.addWidget(self._tts_volume_val)
        tts_layout.addRow("Volume:", vol_row)

        layout.addWidget(tts_group)
        layout.addStretch()

        self._tabs.addTab(tab, "🎙️ Voice & Audio")

    def _init_ai_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        ai_group = QGroupBox("AI Reasoning & Model Configuration")
        ai_layout = QFormLayout(ai_group)
        ai_layout.setSpacing(10)

        self._ai_provider = QComboBox()
        self._ai_provider.addItems(["mock", "openai", "groq", "ollama"])
        idx = self._ai_provider.findText(self.config.ai.provider)
        if idx >= 0:
            self._ai_provider.setCurrentIndex(idx)
        ai_layout.addRow("AI Provider:", self._ai_provider)

        self._ai_model = QLineEdit(self.config.ai.model_name)
        ai_layout.addRow("Model Name:", self._ai_model)

        self._ai_base_url = QLineEdit(self.config.ai.base_url or "")
        self._ai_base_url.setPlaceholderText(
            "https://api.openai.com/v1 (or Ollama http://localhost:11434/v1)"
        )
        ai_layout.addRow("Base URL:", self._ai_base_url)

        self._ai_key = QLineEdit(self.config.ai.api_key or "")
        self._ai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_key.setPlaceholderText("sk-... (optional for local models)")
        ai_layout.addRow("API Key:", self._ai_key)

        self._ai_max_turns = QSpinBox()
        self._ai_max_turns.setRange(2, 50)
        self._ai_max_turns.setValue(self.config.ai.max_conversation_turns)
        ai_layout.addRow("Max Turns:", self._ai_max_turns)

        self._ai_max_tools = QSpinBox()
        self._ai_max_tools.setRange(1, 10)
        self._ai_max_tools.setValue(self.config.ai.max_tool_iterations)
        ai_layout.addRow("Max Tool Loops:", self._ai_max_tools)

        layout.addWidget(ai_group)
        layout.addStretch()

        self._tabs.addTab(tab, "🧠 AI Reasoning")

    def _init_security_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Allowed directories
        dirs_group = QGroupBox("Allowed Filesystem Directories")
        dirs_layout = QVBoxLayout(dirs_group)
        dirs_layout.setSpacing(8)

        self._dirs_list = QListWidget()
        for d in self.config.security.allowed_directories:
            self._dirs_list.addItem(d)
        dirs_layout.addWidget(self._dirs_list)

        dir_btns = QHBoxLayout()
        self._add_dir_btn = QPushButton("Add Folder...")
        self._add_dir_btn.clicked.connect(self._add_directory)
        self._rem_dir_btn = QPushButton("Remove Selected")
        self._rem_dir_btn.clicked.connect(self._remove_directory)
        dir_btns.addWidget(self._add_dir_btn)
        dir_btns.addWidget(self._rem_dir_btn)
        dir_btns.addStretch()
        dirs_layout.addLayout(dir_btns)

        layout.addWidget(dirs_group)

        # Confirmation toggle
        self._confirm_actions = QCheckBox(
            "Require explicit confirmation before destructive system/file actions"
        )
        self._confirm_actions.setChecked(self.config.security.confirm_sensitive_actions)
        layout.addWidget(self._confirm_actions)

        layout.addStretch()
        self._tabs.addTab(tab, "🔒 Security & Tools")

    def _init_ui_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self._ui_visualizer = QCheckBox("Enable dynamic real-time audio visualizer")
        self._ui_visualizer.setChecked(self.config.ui.show_visualizer)
        layout.addRow(self._ui_visualizer)

        self._ui_minimized = QCheckBox("Start minimized in system tray")
        self._ui_minimized.setChecked(self.config.ui.start_minimized)
        layout.addRow(self._ui_minimized)

        self._tabs.addTab(tab, "🖥️ Interface")

    def _add_directory(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Allowed Directory")
        if dir_path:
            norm_path = str(Path(dir_path).resolve())
            items = [self._dirs_list.item(i).text() for i in range(self._dirs_list.count())]
            if norm_path not in items:
                self._dirs_list.addItem(norm_path)

    def _remove_directory(self) -> None:
        selected = self._dirs_list.currentRow()
        if selected >= 0:
            self._dirs_list.takeItem(selected)

    def _save_settings(self) -> None:
        # Update audio settings
        self.config.audio.wake_word_enabled = self._ww_enabled.isChecked()
        self.config.audio.wake_word_phrase = self._ww_phrase.text().strip().lower()
        self.config.audio.wake_word_engine = self._ww_engine.currentText()
        self.config.audio.wake_word_sensitivity = self._ww_sens.value() / 100.0
        self.config.audio.tts_rate = self._tts_rate.value()
        self.config.audio.tts_volume = self._tts_volume.value() / 100.0

        # Update AI settings
        self.config.ai.provider = self._ai_provider.currentText()
        self.config.ai.model_name = self._ai_model.text().strip() or "mock-model"
        base_url = self._ai_base_url.text().strip()
        self.config.ai.base_url = base_url if base_url else None
        api_key = self._ai_key.text().strip()
        self.config.ai.api_key = api_key if api_key else None
        self.config.ai.max_conversation_turns = self._ai_max_turns.value()
        self.config.ai.max_tool_iterations = self._ai_max_tools.value()

        # Update Security settings
        dirs: list[str] = [self._dirs_list.item(i).text() for i in range(self._dirs_list.count())]
        self.config.security.allowed_directories = dirs
        self.config.security.confirm_sensitive_actions = self._confirm_actions.isChecked()

        # Update UI settings
        self.config.ui.show_visualizer = self._ui_visualizer.isChecked()
        self.config.ui.start_minimized = self._ui_minimized.isChecked()

        # Persist to disk
        try:
            save_config(self.config, config_path=self.config_path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Could not persist configuration to disk: {exc}",
            )

        self.settings_saved.emit(self.config)
        self.accept()
