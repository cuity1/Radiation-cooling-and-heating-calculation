"""Reusable custom Qt widgets."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QPropertyAnimation, pyqtProperty
from PyQt5.QtGui import QColor, QCursor
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
    QSizePolicy,
)

from .i18n import COLORS


class AnimatedButton(QPushButton):
    """A button with color fade animations for hover/press states."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._normal_color = QColor(COLORS['accent'])
        self._hover_color = QColor('#2980B9')  # Darker accent
        self._pressed_color = QColor('#21618C')  # Even darker
        self._current_color = self._normal_color

        self._animation = QPropertyAnimation(self, b'background_color')
        self._animation.setDuration(200)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.background_color = self._normal_color  # Apply initial stylesheet

    @pyqtProperty(QColor)
    def background_color(self) -> QColor:
        return self._current_color

    @background_color.setter
    def background_color(self, color: QColor) -> None:
        self._current_color = color
        self.setStyleSheet(
            f"""QPushButton {{
                background-color: {color.name()};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-height: 30px;
            }}"""
        )

    def enterEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._hover_color)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._normal_color)
        self._animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._animation.stop()
            self._animation.setStartValue(self._current_color)
            self._animation.setEndValue(self._pressed_color)
            self._animation.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._animation.stop()
            self._animation.setStartValue(self._current_color)
            self._animation.setEndValue(
                self._hover_color if self.underMouse() else self._normal_color
            )
            self._animation.start()
        super().mouseReleaseEvent(event)


class TitleLabel(QLabel):
    """A QLabel with a title-like appearance and a drop shadow."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName('title')
        self.setAlignment(Qt.AlignCenter)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)


class CardFrame(QFrame):
    """A QFrame styled as a card with a drop shadow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"""CardFrame {{
                background-color: {COLORS['card']};
                border-radius: 8px;
                padding: 10px;
            }}"""
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)


# Global application stylesheet
STYLE_SHEET = f"""
    QMainWindow {{
        background-color: {COLORS['background']};
    }}
    QWidget {{
        background-color: {COLORS['background']};
        color: {COLORS['primary_text']};
    }}
    QGroupBox {{
        font-weight: bold;
        border: 2px solid {COLORS['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 12px;
        background-color: {COLORS['card']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {COLORS['accent']};
    }}
    QPushButton {{
        background-color: {COLORS['accent']};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-size: 12px;
        font-weight: 500;
        min-width: 120px;
    }}
    QPushButton:hover {{
        background-color: #2980B9;
    }}
    QPushButton:pressed {{
        background-color: #21618C;
    }}
    QLabel {{
        color: {COLORS['primary_text']};
    }}
    QLineEdit, QTextEdit {{
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        padding: 6px;
        background-color: {COLORS['card']};
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 2px solid {COLORS['accent']};
    }}
    QTabWidget::pane {{
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        background-color: {COLORS['card']};
    }}
    QTabBar::tab {{
        background-color: {COLORS['light_bg']};
        color: {COLORS['secondary_text']};
        padding: 8px 16px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {COLORS['card']};
        color: {COLORS['accent']};
        font-weight: bold;
    }}
"""