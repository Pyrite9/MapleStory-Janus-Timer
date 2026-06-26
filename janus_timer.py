"""
MapleStory Janus Timer

게임 스킬 쿨다운을 감지하고 표시하는 데스크톱 오버레이 타이머.
지정한 키 입력을 전역에서 감지해 쿨다운 카운트다운을 띄우고, 완료 시
알림음을 울린다. 일반 창과 '클릭이 통과하는 투명 오버레이'라는 두 얼굴을
단축키로 오가므로 Janus(두 얼굴의 신)에서 이름을 따왔다.

주요 기능
  - 전역 키 감지로 쿨다운 시작 (쿨다운 중 재입력은 무시)
  - 카운트다운 숫자 + 배경이 아래에서 위로 밝아지는 진행 연출 + 완료 알림음(wav/mp3)
  - 일반 / 오버레이(투명·항상 위·클릭 통과) 모드 토글
  - 설정창에서 키·시간·크기·이미지·알림음·투명도 편집 후 즉시 반영
  - 설정은 스크립트 폴더의 settings.json에 저장

조작
  - 트리거 키          : 쿨다운 시작 (기본 3)
  - Ctrl+Alt+O         : 오버레이 모드 토글 (설정에서 변경 가능)
  - 우클릭(일반 모드)  : 오버레이 전환 / 설정 / 종료
  - 본문 드래그        : 위치 이동 (일반 모드)

요구사항 : Python 3.9+, PySide6, pynput
실행     : pip install PySide6 pynput  →  python janus_timer.py
"""

import sys
import os
import math
import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QUrl
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QAction, QKeySequence,
    QPainterPath, QPen, QFontMetricsF,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QApplication, QWidget, QMenu, QDialog, QFormLayout, QHBoxLayout,
    QVBoxLayout, QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QLabel, QMessageBox, QFileDialog, QGroupBox, QSlider, QLayout,
)

from pynput import keyboard


# --- 앱 메타 / 경로 --------------------------------------------------------
APP_NAME = "Janus Timer"
if getattr(sys, "frozen", False):
    # PyInstaller로 묶인 exe로 실행될 때: exe가 놓인 폴더 기준
    # (--onefile의 임시 추출 폴더가 아니라, 설정/리소스가 영속되는 위치)
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # 일반 .py 실행: 스크립트가 있는 폴더 기준
    BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "settings.json"

# --- 동작 상수 -------------------------------------------------------------
TICK_INTERVAL_MS = 100                # 카운트다운 갱신 주기(ms)
PROMPT_TEXT = "키를 누르세요..."        # 키 캡처 대기 안내 문구

# --- 카운트다운 렌더링 -----------------------------------------------------
COUNTDOWN_FONT = "Arial Black"
COUNTDOWN_FILL = "yellow"
COUNTDOWN_OUTLINE = "black"
OUTLINE_RATIO = 0.015                 # 외곽선 두께 = 창 높이 × 이 비율
OUTLINE_MIN = 1.5
SOLID_BG = "#1a1a1a"                  # 일반 모드에서 이미지가 없을 때의 단색 배경
OVERLAY_DARK_ALPHA = 160             # 쿨다운 진행 중 덮는 회색의 알파(0~255)


def resolve_path(path_str: str) -> Path:
    """상대경로면 스크립트 폴더 기준으로 절대경로화."""
    p = Path(path_str)
    return p if p.is_absolute() else (BASE_DIR / p)


def hotkey_display(hotkey: str) -> str:
    """pynput 포맷('<ctrl>+<alt>+o')을 사람이 읽기 쉬운 'Ctrl+Alt+O'로."""
    parts = []
    for p in hotkey.split("+"):
        p = p.strip().strip("<>")
        parts.append(p.upper() if len(p) == 1 else p.capitalize())
    return "+".join(parts)


# --- 다크 테마(Catppuccin Mocha 계열) -------------------------------------
DIALOG_QSS = """
QDialog { background-color: #1e1e2e; }
QGroupBox {
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px; padding: 0 4px;
    color: #89b4fa;
}
QLabel { color: #cdd6f4; }
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #313244; color: #cdd6f4;
    border: 1px solid #45475a; border-radius: 4px;
    padding: 4px 6px; min-height: 22px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #89b4fa; }
QPushButton {
    background-color: #45475a; color: #cdd6f4;
    border: none; border-radius: 4px; padding: 6px 16px; min-height: 24px;
}
QPushButton:hover { background-color: #585b70; }
QPushButton:pressed { background-color: #6c7086; }
QCheckBox { color: #cdd6f4; spacing: 6px; }
QSlider::groove:horizontal { height: 6px; background: #313244; border-radius: 3px; }
QSlider::handle:horizontal { background: #89b4fa; width: 14px; margin: -5px 0; border-radius: 7px; }
QSlider::sub-page:horizontal { background: #74c7ec; border-radius: 3px; }
"""

MENU_QSS = """
QMenu { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background-color: #45475a; }
QMenu::separator { height: 1px; background: #45475a; margin: 4px 6px; }
"""

# 키 캡처 대기 중 강조(노란 테두리)
CAPTURING_QSS = "QLineEdit { border: 2px solid #f9e2af; background-color: #313244; color: #cdd6f4; }"


# ---------------------------------------------------------------------------
# 키 이름 변환: Qt 키코드 → pynput 이름.
#   여기 없는 키(문자/숫자)는 QKeySequence 문자열을 그대로 쓴다('a', '3' 등).
#   여기 있는 키는 pynput Key 이름으로 강제하고, 조합키 안에선 <...>로 감싼다.
# ---------------------------------------------------------------------------
QT_TO_PYNPUT = {
    Qt.Key_F1: "f1", Qt.Key_F2: "f2", Qt.Key_F3: "f3", Qt.Key_F4: "f4",
    Qt.Key_F5: "f5", Qt.Key_F6: "f6", Qt.Key_F7: "f7", Qt.Key_F8: "f8",
    Qt.Key_F9: "f9", Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
    Qt.Key_Space: "space",
    Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
    Qt.Key_Tab: "tab",
    Qt.Key_Escape: "esc",
    Qt.Key_Backspace: "backspace",
    Qt.Key_Delete: "delete",
    Qt.Key_Insert: "insert",
    Qt.Key_Home: "home", Qt.Key_End: "end",
    Qt.Key_PageUp: "page_up", Qt.Key_PageDown: "page_down",
    Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right",
}

_MOD_KEYS = (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta)


def qt_key_to_name(key: int):
    """(이름, 특수키여부) 반환. 변환 실패 시 (None, False)."""
    if key in QT_TO_PYNPUT:
        return QT_TO_PYNPUT[key], True
    text = QKeySequence(key).toString().lower()
    return (text, False) if text else (None, False)


# ---------------------------------------------------------------------------
# 설정 (dataclass + json). 알 수 없는 키는 무시, 깨졌으면 기본값 복구.
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    trigger_key: str = "3"
    toggle_hotkey: str = "<ctrl>+<alt>+o"
    cooldown_sec: float = 55.0
    window_width: int = 200
    window_height: int = 200
    always_on_top: bool = True
    image_path: str = "background.png"
    sound_path: str = "alarm.wav"
    volume_pct: int = 100
    opacity_pct: int = 100
    lock_ratio: bool = True
    overlay_mode: bool = False
    pos_x: int = -1
    pos_y: int = -1

    @classmethod
    def load(cls) -> "Settings":
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                return cls(**{k: v for k, v in data.items() if k in known})
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"[설정] 로드 실패, 기본값 사용: {e}")
        return cls()

    def save(self) -> None:
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self), indent=4, ensure_ascii=False),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# 키 브릿지: pynput(백그라운드 스레드) → Qt Signal(메인스레드).
#   - trigger_key 단일 키: 쿨다운 시작
#   - toggle_hotkey 조합키: 오버레이 전환
# 둘 다 신호만 쏘고 실제 처리는 메인 이벤트 루프에서 → race condition 없음.
# ---------------------------------------------------------------------------
class KeyBridge(QObject):
    triggered = Signal()
    toggle_requested = Signal()

    def __init__(self, trigger_key: str, toggle_hotkey: str):
        super().__init__()
        self.trigger_key = trigger_key
        self._listener = keyboard.Listener(on_press=self._on_press)
        try:
            self._hotkeys = keyboard.GlobalHotKeys(
                {toggle_hotkey: self.toggle_requested.emit}
            )
        except ValueError as e:
            print(f"[단축키] '{toggle_hotkey}' 파싱 실패 → 토글 비활성: {e}")
            self._hotkeys = None

    def start(self) -> None:
        self._listener.start()
        if self._hotkeys:
            self._hotkeys.start()

    def stop(self) -> None:
        self._listener.stop()
        if self._hotkeys:
            self._hotkeys.stop()

    def _on_press(self, key) -> None:
        try:
            pressed = key.char if getattr(key, "char", None) else str(key).replace("Key.", "")
        except AttributeError:
            return
        if pressed == self.trigger_key:
            self.triggered.emit()


# ---------------------------------------------------------------------------
# 키 캡처 입력칸: 클릭하면 키 입력 대기, 누른 키를 표시.
#   combo=False → 단일 키 ('3', 'f2' ...)
#   combo=True  → 조합키 ('<ctrl>+<alt>+o' ...)  modifier 단독은 무시하고 대기.
# ---------------------------------------------------------------------------
class KeyCaptureEdit(QLineEdit):
    def __init__(self, combo: bool = False, parent=None):
        super().__init__(parent)
        self.combo = combo
        self.capturing = False
        self._prev = ""
        self.setReadOnly(True)
        self.setPlaceholderText("클릭 후 키 입력")

    def mousePressEvent(self, e):
        self._prev = self.text()
        self.capturing = True
        self.setText(PROMPT_TEXT)
        self.setStyleSheet(CAPTURING_QSS)   # 대기 중 노란 테두리 강조
        self.setFocus()

    def keyPressEvent(self, e):
        if not self.capturing:
            return
        key = e.key()
        if key in _MOD_KEYS:
            return  # modifier 단독은 조합 완성 전이므로 대기
        name, is_special = qt_key_to_name(key)
        if not name:
            return
        if self.combo:
            mods = e.modifiers()
            parts = []
            if mods & Qt.ControlModifier:
                parts.append("<ctrl>")
            if mods & Qt.AltModifier:
                parts.append("<alt>")
            if mods & Qt.ShiftModifier:
                parts.append("<shift>")
            # 조합키 안의 특수키는 pynput 문법상 <...>로 감싼다. 문자는 그대로.
            parts.append(f"<{name}>" if is_special else name)
            self.setText("+".join(parts))
        else:
            # 트리거 단일 키: pynput Key 이름(꺾쇠 없음) 또는 문자 그대로.
            self.setText(name)
        self._end_capture()

    def focusOutEvent(self, e):
        if self.capturing:                  # 캡처 도중 포커스 이탈 → 취소, 원래 값 복원
            self.setText(self._prev)
            self._end_capture()
        super().focusOutEvent(e)

    def _end_capture(self):
        self.capturing = False
        self.setStyleSheet("")              # 다이얼로그 기본 테마로 복귀
        self.clearFocus()


# ---------------------------------------------------------------------------
# 설정 다이얼로그: 값만 편집해서 돌려준다. 적용은 타이머 위젯이 한다.
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(f"{APP_NAME} 설정")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setStyleSheet(DIALOG_QSS)
        self._build()

    @staticmethod
    def _group(title: str, form: QFormLayout) -> QGroupBox:
        box = QGroupBox(title)
        box.setLayout(form)
        return box

    def _build(self):
        # --- 위젯 ---
        self.trigger_edit = KeyCaptureEdit(combo=False)
        self.trigger_edit.setText(self.settings.trigger_key)
        self.trigger_edit.setToolTip("쿨다운을 시작할 키 하나를 눌러 지정")
        self.toggle_edit = KeyCaptureEdit(combo=True)
        self.toggle_edit.setText(self.settings.toggle_hotkey)
        self.toggle_edit.setToolTip("Ctrl/Alt/Shift + 키 조합을 눌러 지정")

        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.1, 3600.0)
        self.cooldown_spin.setDecimals(1)
        self.cooldown_spin.setValue(self.settings.cooldown_sec)
        self.cooldown_spin.setToolTip("쿨다운 길이(초)")

        self.w_spin = QSpinBox(); self.w_spin.setRange(20, 4000); self.w_spin.setValue(self.settings.window_width)
        self.h_spin = QSpinBox(); self.h_spin.setRange(20, 4000); self.h_spin.setValue(self.settings.window_height)
        self.lock_ratio = QCheckBox("1:1 고정")
        self.lock_ratio.setChecked(self.settings.lock_ratio)
        self.lock_ratio.setToolTip("켜면 가로·세로가 같은 정사각으로 유지")
        size_row = QHBoxLayout()
        size_row.addWidget(self.w_spin); size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.h_spin); size_row.addWidget(self.lock_ratio)
        # 잠금 상태면 한쪽 변경이 다른 쪽을 따라오게(blockSignals로 무한루프 방지)
        self.w_spin.valueChanged.connect(self._sync_from_w)
        self.h_spin.valueChanged.connect(self._sync_from_h)
        self.lock_ratio.toggled.connect(self._on_lock_toggled)
        if self.settings.lock_ratio:
            self.h_spin.setValue(self.w_spin.value())

        self.image_edit = QLineEdit(self.settings.image_path)
        self.image_edit.setToolTip("비우거나 경로가 없으면 단색/투명 배경")
        img_browse = QPushButton("찾기"); img_browse.clicked.connect(self._browse_image)
        img_row = QHBoxLayout(); img_row.addWidget(self.image_edit); img_row.addWidget(img_browse)

        self.aot_check = QCheckBox("항상 다른 창 위에 표시")
        self.aot_check.setChecked(self.settings.always_on_top)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(self.settings.opacity_pct)
        self.opacity_slider.setToolTip("배경 이미지와 쿨다운 회색 오버레이의 불투명도")
        self.opacity_label = QLabel(f"{self.settings.opacity_pct}%")
        self.opacity_label.setMinimumWidth(40)
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity_slider); opacity_row.addWidget(self.opacity_label)

        self.sound_edit = QLineEdit(self.settings.sound_path)
        self.sound_edit.setToolTip("비우거나 경로가 없으면 기본 비프음")
        snd_browse = QPushButton("찾기"); snd_browse.clicked.connect(self._browse_sound)
        snd_row = QHBoxLayout(); snd_row.addWidget(self.sound_edit); snd_row.addWidget(snd_browse)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(min(self.settings.volume_pct, 100))
        self.vol_slider.setToolTip("알림음 볼륨")
        self.vol_label = QLabel(f"{self.settings.volume_pct}%")
        self.vol_label.setMinimumWidth(40)
        self.vol_slider.valueChanged.connect(lambda v: self.vol_label.setText(f"{v}%"))
        vol_row = QHBoxLayout(); vol_row.addWidget(self.vol_slider); vol_row.addWidget(self.vol_label)

        # --- 그룹 ---
        key_form = QFormLayout()
        key_form.addRow("트리거 키:", self.trigger_edit)
        key_form.addRow("오버레이 토글:", self.toggle_edit)

        timer_form = QFormLayout()
        timer_form.addRow("쿨다운(초):", self.cooldown_spin)

        disp_form = QFormLayout()
        disp_form.addRow("창 크기:", size_row)
        disp_form.addRow("배경 이미지:", img_row)
        disp_form.addRow("투명도:", opacity_row)
        disp_form.addRow("", self.aot_check)

        snd_form = QFormLayout()
        snd_form.addRow("알림음 파일:", snd_row)
        snd_form.addRow("볼륨:", vol_row)

        for f in (key_form, timer_form, disp_form, snd_form):
            f.setVerticalSpacing(8)
            f.setHorizontalSpacing(10)
            f.setContentsMargins(4, 4, 4, 4)

        # --- 버튼 ---
        save_btn = QPushButton("저장"); save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("취소"); cancel_btn.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch(); btn_row.addWidget(save_btn); btn_row.addWidget(cancel_btn)

        outer = QVBoxLayout(self)
        outer.setSizeConstraint(QLayout.SetFixedSize)   # 콘텐츠 크기로 고정, 리사이즈 차단
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        outer.addWidget(self._group("키 설정", key_form))
        outer.addWidget(self._group("타이머", timer_form))
        outer.addWidget(self._group("표시", disp_form))
        outer.addWidget(self._group("알림음", snd_form))
        outer.addLayout(btn_row)

    # --- 창 크기 비율 잠금 ------------------------------------------------
    def _sync_from_w(self, v):
        if self.lock_ratio.isChecked() and self.h_spin.value() != v:
            self.h_spin.blockSignals(True); self.h_spin.setValue(v); self.h_spin.blockSignals(False)

    def _sync_from_h(self, v):
        if self.lock_ratio.isChecked() and self.w_spin.value() != v:
            self.w_spin.blockSignals(True); self.w_spin.setValue(v); self.w_spin.blockSignals(False)

    def _on_lock_toggled(self, checked):
        if checked:                       # 잠그는 순간 세로를 가로에 맞춰 정사각으로
            self.h_spin.setValue(self.w_spin.value())

    # --- 파일 선택 --------------------------------------------------------
    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "배경 이미지 선택", str(BASE_DIR),
            "이미지 (*.png *.jpg *.jpeg *.bmp *.gif);;모든 파일 (*)",
        )
        if path:
            self.image_edit.setText(path)

    def _browse_sound(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "알림음 선택", str(BASE_DIR),
            "오디오 (*.mp3 *.wav *.ogg *.m4a *.flac);;모든 파일 (*)",
        )
        if path:
            self.sound_edit.setText(path)

    # --- 저장 / 반영 ------------------------------------------------------
    def _on_save(self):
        trigger = self.trigger_edit.text().strip()
        toggle = self.toggle_edit.text().strip()
        if not trigger or trigger == PROMPT_TEXT:
            QMessageBox.warning(self, "입력 오류", "트리거 키를 지정해줘."); return
        if "+" not in toggle:
            QMessageBox.warning(self, "입력 오류",
                                "오버레이 토글은 조합키여야 해 (예: <ctrl>+<alt>+o)."); return
        self.accept()

    def apply_to(self, s: Settings) -> None:
        s.trigger_key = self.trigger_edit.text().strip()
        s.toggle_hotkey = self.toggle_edit.text().strip()
        s.cooldown_sec = self.cooldown_spin.value()
        s.window_width = self.w_spin.value()
        s.window_height = self.h_spin.value()
        s.image_path = self.image_edit.text().strip()
        s.sound_path = self.sound_edit.text().strip()
        s.volume_pct = self.vol_slider.value()
        s.opacity_pct = self.opacity_slider.value()
        s.lock_ratio = self.lock_ratio.isChecked()
        s.always_on_top = self.aot_check.isChecked()


# ---------------------------------------------------------------------------
# 타이머 위젯
# ---------------------------------------------------------------------------
class TimerWidget(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.remaining = 0.0
        self.is_cooling = False
        self.overlay_mode = settings.overlay_mode
        self._drag_offset = None

        self._pixmap = self._load_pixmap()

        self._audio_out = QAudioOutput()
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_out)
        self._apply_volume()

        self.tick = QTimer(self)
        self.tick.setInterval(TICK_INTERVAL_MS)
        self.tick.timeout.connect(self._on_tick)

        self.bridge = None
        self._restart_bridge()

        # 투명 배경은 처음부터 항상 켜둔다. 모드 전환마다 토글하면 Windows에서
        # 레이어드 윈도우 오류(UpdateLayeredWindowIndirect)가 나므로 1회만 설정.
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(settings.window_width, settings.window_height)
        if settings.pos_x >= 0 and settings.pos_y >= 0:
            self.move(settings.pos_x, settings.pos_y)
        self._apply_mode()

    # --- 리스너 ----------------------------------------------------------
    def _restart_bridge(self) -> None:
        if self.bridge is not None:
            self.bridge.stop()
        self.bridge = KeyBridge(self.settings.trigger_key, self.settings.toggle_hotkey)
        self.bridge.triggered.connect(self.start_cooldown)
        self.bridge.toggle_requested.connect(self.toggle_overlay)
        self.bridge.start()

    # --- 이미지 ----------------------------------------------------------
    def _load_pixmap(self):
        p = resolve_path(self.settings.image_path)
        if p.exists():
            pix = QPixmap(str(p))
            if not pix.isNull():
                print(f"[이미지] 로드 성공: {p}")
                return pix
            print(f"[이미지] 파일은 있으나 로드 실패(형식/확장자 확인): {p}")
        else:
            print(f"[이미지] 경로 없음: {p}  → 단색 배경(일반)/투명(오버레이)")
        return None

    # --- 알림음 ----------------------------------------------------------
    def _apply_volume(self) -> None:
        # 0~100% 선형. Qt setVolume은 0.0~1.0 범위.
        self._audio_out.setVolume(self.settings.volume_pct / 100.0)

    def _play_alert(self) -> None:
        p = resolve_path(self.settings.sound_path)
        if not p.exists():
            print(f"[사운드] 경로 없음: {p} → 기본 비프음")
            QApplication.beep()
            return
        src = QUrl.fromLocalFile(str(p))
        if self._player.source() != src:
            self._player.setSource(src)
        self._player.setPosition(0)
        self._player.play()

    # --- 모드 ------------------------------------------------------------
    def _apply_mode(self) -> None:
        """플래그를 바꾸려면 창을 다시 만들어야 해서 hide→설정→show 순서.
        투명 속성은 건드리지 않는다(항상 켜진 상태). 클릭 통과 플래그만 토글."""
        self.setWindowTitle(APP_NAME)
        self.hide()
        flags = Qt.FramelessWindowHint
        if self.overlay_mode:
            flags |= Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.Tool
        elif self.settings.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def toggle_overlay(self) -> None:
        self.overlay_mode = not self.overlay_mode
        self.settings.overlay_mode = self.overlay_mode
        self.settings.save()
        self._apply_mode()
        print(f"오버레이 모드: {'ON' if self.overlay_mode else 'OFF'}")

    # --- 설정 ------------------------------------------------------------
    def open_settings(self) -> None:
        # 설정창이 떠 있는 동안 전역 리스너를 멈춰 키 캡처와 충돌하지 않게.
        self.bridge.stop()
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply_to(self.settings)
            self.settings.save()
            self.setFixedSize(self.settings.window_width, self.settings.window_height)
            self._pixmap = self._load_pixmap()
            self._player.setSource(QUrl())   # 사운드 경로 캐시 비움
            self._apply_volume()
            self._apply_mode()
            self.update()
        # 변경 여부와 무관하게 새 설정으로 리스너 재시작
        self._restart_bridge()

    # --- 쿨다운 ----------------------------------------------------------
    def start_cooldown(self) -> None:
        # 메인스레드에서만 호출 → 체크와 상태 변경 사이에 끼어들 스레드가 없다.
        if self.is_cooling:
            return  # 쿨다운 중 재입력 무시
        self.is_cooling = True
        self.remaining = self.settings.cooldown_sec
        self.tick.start()
        self.update()

    def _on_tick(self) -> None:
        self.remaining -= TICK_INTERVAL_MS / 1000.0
        if self.remaining <= 0:
            self.remaining = 0.0
            self.is_cooling = False
            self.tick.stop()
            self._play_alert()
            print("쿨다운 완료")
        self.update()

    # --- 그리기 ----------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        opacity = self.settings.opacity_pct / 100.0

        # 배경(이미지/단색): 투명도 적용
        painter.setOpacity(opacity)
        if self._pixmap:
            painter.drawPixmap(
                0, 0,
                self._pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation),
            )
        elif not self.overlay_mode:
            painter.fillRect(self.rect(), QColor(SOLID_BG))
        painter.setOpacity(1.0)

        if self.is_cooling:
            # 진행 연출: 아직 안 지난 만큼(위쪽)을 어둡게 덮는다(배경과 같은 투명도).
            progress = 1.0 - self.remaining / self.settings.cooldown_sec
            dark_h = int(h * (1.0 - progress))
            if dark_h > 0:
                painter.setOpacity(opacity)
                painter.fillRect(0, 0, w, dark_h, QColor(0, 0, 0, OVERLAY_DARK_ALPHA))
                painter.setOpacity(1.0)

            # 카운트다운 숫자는 투명도 영향 없이 또렷하게.
            # 글자를 경로로 만들어 중앙 정렬 후, 검은 외곽선 + 노란 채움.
            text = str(math.ceil(self.remaining))
            font = QFont(COUNTDOWN_FONT, max(20, h // 4))
            fm = QFontMetricsF(font)
            x = (w - fm.horizontalAdvance(text)) / 2.0
            y = (h + fm.ascent() - fm.descent()) / 2.0   # 수직 중앙(baseline 보정)
            path = QPainterPath()
            path.addText(x, y, font, text)

            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(COUNTDOWN_OUTLINE))
            pen.setWidthF(max(OUTLINE_MIN, h * OUTLINE_RATIO))   # 외곽선 두께는 창 높이에 비례
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QColor(COUNTDOWN_FILL))
            painter.drawPath(path)

    # --- 마우스(일반 모드 전용; 오버레이는 클릭 통과라 이벤트가 안 옴) -----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e):
        if self._drag_offset is not None:
            self._drag_offset = None
            self.settings.pos_x = self.x()
            self.settings.pos_y = self.y()
            self.settings.save()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_QSS)
        hk = hotkey_display(self.settings.toggle_hotkey)
        label = ("오버레이 끄기" if self.overlay_mode else "오버레이 켜기") + f" ({hk})"
        act_overlay = QAction(label, self)
        act_settings = QAction("설정", self)
        act_quit = QAction("종료", self)
        menu.addAction(act_overlay)
        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction(act_quit)
        chosen = menu.exec(event.globalPos())
        if chosen == act_overlay:
            self.toggle_overlay()
        elif chosen == act_settings:
            self.open_settings()
        elif chosen == act_quit:
            self.close()

    def closeEvent(self, event):
        self.bridge.stop()
        QApplication.quit()
        super().closeEvent(event)


def main():
    # --windowed(콘솔 없음) exe에서는 표준 출력이 없어 print가 예외를 낼 수 있으므로 무력화.
    if sys.stdout is None:
        sys.stdout = sys.stderr = open(os.devnull, "w")
    settings = Settings.load()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    widget = TimerWidget(settings)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
