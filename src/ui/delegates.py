# -*- coding: utf-8 -*-
"""
Custom Item Delegates for QTableWidget/QTableView.
"""

from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont

from ui.styles.tokens import (
    BOX_COLORS, PILL_COLORS, TEXT_PRIMARY, TEXT_INVERSE,
    FONT_BODY, FONT_SIZE_CAPTION, RADIUS_SM
)

class BadgeDelegate(QStyledItemDelegate):
    """
    Renders text inside a rounded badge (pill).

    Uses UserRole data to determine the badge color key.
    If UserRole is not set, falls back to a default color.
    """

    def __init__(self, parent=None, color_map=None):
        super().__init__(parent)
        self.color_map = color_map or {}
        self.default_color = "#e2e8f0"  # Gray-200
        self.default_text_color = "#475569" # Slate-600
        self.padding_x = 8
        self.padding_y = 4

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint the badge."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background (handle selection)
        if option.state & QStyleOptionViewItem.State.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.palette.base())

        # Get data
        text = index.data(Qt.ItemDataRole.DisplayRole)
        color_key = index.data(Qt.ItemDataRole.UserRole)

        if not text:
            painter.restore()
            return

        # Determine colors
        bg_color = QColor(self.default_color)
        text_color = QColor(self.default_text_color)

        if color_key:
            # Check if color_key is in our map (which might map to a hex string or a dict)
            mapped = self.color_map.get(color_key)
            if mapped:
                if isinstance(mapped, dict):
                    # Expecting {'bg': '#...', 'text': '#...'} style like PILL_COLORS
                    bg_color = QColor(mapped.get('bg', self.default_color))
                    text_color = QColor(mapped.get('text', self.default_text_color))
                elif isinstance(mapped, str):
                    # Expecting direct hex string
                    bg_color = QColor(mapped)
                    # Simple contrast logic for text color if only bg is provided
                    text_color = QColor(TEXT_INVERSE) if bg_color.lightness() < 128 else QColor(TEXT_PRIMARY)

        # Calculate badge rect
        rect = option.rect
        font = QFont(FONT_BODY)
        # Use a slightly smaller font for badges
        font.setPixelSize(11) # approx FONT_SIZE_CAPTION
        painter.setFont(font)

        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance(text)
        text_height = font_metrics.height()

        badge_width = text_width + (self.padding_x * 2)
        badge_height = text_height + (self.padding_y * 1.5)

        # Center the badge
        x = rect.x() + (rect.width() - badge_width) / 2
        y = rect.y() + (rect.height() - badge_height) / 2

        badge_rect = QRectF(x, y, badge_width, badge_height)

        # Draw Badge Background
        path = Qt.QPainterPath()
        radius = 4.0 # RADIUS_SM
        path.addRoundedRect(badge_rect, radius, radius)

        painter.fillPath(path, QBrush(bg_color))

        # Draw Text
        painter.setPen(QPen(text_color))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()

    def sizeHint(self, option, index):
        """Return size hint with padding."""
        size = super().sizeHint(option, index)
        return QSize(size.width() + 20, size.height() + 10)
