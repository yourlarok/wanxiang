import argparse
import base64
import html
import json
import platform
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from pynput import keyboard, mouse
from PySide6.QtCore import QBuffer, QIODevice, QObject, QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


DARK_STYLES = {"textbook", "blueprint", "chalk", "pixel"}


def encode_pixmap(pixmap: QPixmap, image_format: str = "PNG", max_width: int = 1800) -> str:
    if pixmap.width() > max_width:
        pixmap = pixmap.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, image_format, 88)
    encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
    mime = "jpeg" if image_format.upper() in {"JPG", "JPEG"} else "png"
    return f"data:image/{mime};base64,{encoded}"


def capture_screen(screen, geometry: QRect | None = None) -> QPixmap:
    region = geometry or screen.geometry()
    if sys.platform == "darwin":
        import Quartz
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectMake(region.x(), region.y(), region.width(), region.height()),
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageDefault,
        )
        if not image:
            return QPixmap()
        width = Quartz.CGImageGetWidth(image)
        height = Quartz.CGImageGetHeight(image)
        provider = Quartz.CGImageGetDataProvider(image)
        data = bytes(Quartz.CGDataProviderCopyData(provider))
        stride = Quartz.CGImageGetBytesPerRow(image)
        native = QImage(data, width, height, stride, QImage.Format.Format_ARGB32_Premultiplied).copy()
        pixmap = QPixmap.fromImage(native)
        pixmap.setDevicePixelRatio(width / max(1, region.width()))
        return pixmap
    return screen.grabWindow(0, region.x(), region.y(), region.width(), region.height())


def frosted_pixmap(pixmap: QPixmap) -> QPixmap:
    source = pixmap.toImage()
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(source))
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(32)
    blur.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(blur)
    scene.addItem(item)
    blurred = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
    blurred.fill(Qt.GlobalColor.transparent)
    painter = QPainter(blurred)
    scene.render(painter, QRectF(blurred.rect()), QRectF(source.rect()))
    painter.end()
    result = QPixmap.fromImage(blurred)
    result.setDevicePixelRatio(pixmap.devicePixelRatio())
    return result


def permission_status() -> dict[str, bool | str]:
    if sys.platform != "darwin":
        return {"screen": True, "input": True, "platform": platform.system()}
    try:
        import Quartz
        from ApplicationServices import AXIsProcessTrustedWithOptions
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectMake(0, 0, 2, 2), Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault,
        )
        readable = bool(image and Quartz.CGImageGetWidth(image) > 0)
        return {
            "screen": bool(Quartz.CGPreflightScreenCaptureAccess()) and readable,
            "input": bool(AXIsProcessTrustedWithOptions(None)),
            "platform": "macOS",
        }
    except ImportError:
        return {"screen": False, "input": False, "platform": "macOS"}


class StaticSnapshotReader(QObject):
    def __init__(self, interval_ms: int):
        super().__init__()
        self.snapshots: dict[str, tuple[QPixmap, float]] = {}
        self.suspended = False
        self.timer = QTimer(self)
        self.timer.setInterval(max(1000, interval_ms))
        self.timer.timeout.connect(self.capture_current_screen)

    def start(self) -> None:
        self.capture_current_screen()
        self.timer.start()

    def capture_current_screen(self) -> None:
        if self.suspended:
            return
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if not screen:
            return
        pixmap = capture_screen(screen)
        if not pixmap.isNull():
            self.snapshots[screen.name()] = (pixmap, time.time())

    def latest(self, screen) -> QPixmap | None:
        snapshot = self.snapshots.get(screen.name())
        return snapshot[0] if snapshot else None


class InputBridge(QObject):
    activated = Signal()
    cancelled = Signal()
    pressed = Signal(object)
    moved = Signal(object)
    released = Signal(object)


class MacKeyboardListener:
    def __init__(self, on_shortcut, on_cancel):
        self.on_shortcut = on_shortcut
        self.on_cancel = on_cancel
        self.shortcut_down = False
        self.monitor = None

    def start(self) -> None:
        from AppKit import NSEvent, NSKeyDownMask, NSKeyUpMask

        self.monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSKeyDownMask | NSKeyUpMask,
            self.handle_event,
        )
        if self.monitor is None:
            raise RuntimeError("无法注册 macOS 全局快捷键，请检查辅助功能或输入监控权限")

    def handle_event(self, event) -> None:
        from AppKit import (
            NSKeyDown,
            NSKeyUp,
            NSEventModifierFlagCommand,
            NSEventModifierFlagControl,
            NSEventModifierFlagShift,
        )

        key_code = event.keyCode()
        if key_code == 53 and event.type() == NSKeyDown:
            self.on_cancel()
            return
        if key_code != 7:
            return
        if event.type() == NSKeyUp:
            self.shortcut_down = False
            return
        if event.type() != NSKeyDown or self.shortcut_down:
            return
        flags = event.modifierFlags()
        primary = flags & (NSEventModifierFlagCommand | NSEventModifierFlagControl)
        if flags & NSEventModifierFlagShift and primary:
            self.shortcut_down = True
            self.on_shortcut()


class SelectionOverlay(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.start = QPoint()
        self.current = QPoint()

    def begin(self, position: QPoint, screen) -> None:
        self.setGeometry(screen.geometry())
        self.start = position
        self.current = position
        self.show()
        self.raise_()

    def update_position(self, position: QPoint) -> None:
        self.current = position
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(7, 12, 24, 62))
        selection = QRect(self.mapFromGlobal(self.start), self.mapFromGlobal(self.current)).normalized()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(selection, Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(QPen(QColor(110, 211, 255), 2))
        painter.fillRect(selection, QColor(71, 180, 235, 24))
        painter.drawRect(selection)
        painter.setPen(QColor(235, 247, 255))
        painter.drawText(selection.adjusted(8, 8, -8, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, f"{selection.width()} × {selection.height()}")


class PixelDog(QWidget):
    SPRITE = (
        "       KK          KK       ",
        "      KAAK        KAAK      ",
        "     KAAAAK      KAAAAK     ",
        "     KAAAAAKKKKKKAAAAAK     ",
        "    KAAAAAAAAAAAAAAAAAAAK    ",
        "   KAAAAAAAAAAAAAAAAAAAAAK   ",
        "  KAAADDAAAAAAAAAAAAADDAAAK  ",
        "  KAADDDAAAAAAAAAAAAADDDAAK  ",
        " KAADDDAAEAAAAAAEAAADDDAAK ",
        " KAADDDAAEAAAAAAEAAADDDAAK ",
        " KAAAAAAAAANNNNAAAAAAAAAAK ",
        "KAAAAAAAAANNNNAAAAAAAAAAAK",
        "KAAAAACCCCNNNNCCCCAAAAAAAK",
        "KBBBAACCCCPPCCCCAABBBK",
        "KAAAAAACCCCPPCCCCAAAAAAAK",
        " KAAAAAACCCCCCCCAAAAAAAK ",
        "  KKKAAAAAAAAAAAAAAAKKK  ",
        "    KKKKKKKKKKKKKKKKK    ",
    )
    COLORS = {
        "K": "#17152b",
        "A": "#f4a261",
        "D": "#a76455",
        "E": "#272147",
        "N": "#17152b",
        "C": "#ffe0b2",
        "P": "#ff8fab",
        "B": "#f48c8c",
    }

    def __init__(self):
        super().__init__()
        self.frame = 0
        self.setMinimumSize(190, 132)

    def set_frame(self, frame: int) -> None:
        self.frame = frame
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pixel = 5
        sprite_width = max(len(row) for row in self.SPRITE) * pixel
        origin_x = (self.width() - sprite_width) // 2
        origin_y = 7 + (pixel if self.frame % 4 == 2 else 0)
        blink = self.frame % 12 == 10
        painter.fillRect(QRect(origin_x + 30, origin_y + len(self.SPRITE) * pixel + 3, sprite_width - 60, 5), QColor(8, 7, 17, 150))
        for y, row in enumerate(self.SPRITE):
            for x, value in enumerate(row):
                if value == "E" and blink:
                    painter.fillRect(QRect(origin_x + x * pixel, origin_y + y * pixel + 2, pixel, 2), QColor(self.COLORS["E"]))
                elif value in self.COLORS:
                    painter.fillRect(QRect(origin_x + x * pixel, origin_y + y * pixel, pixel, pixel), QColor(self.COLORS[value]))
        sparkle = QColor("#58dfc0") if self.frame % 2 else QColor("#ffd166")
        for x, y in ((origin_x - 14, 28), (origin_x + sprite_width + 8, 52)):
            painter.fillRect(QRect(x + 4, y, 4, 12), sparkle)
            painter.fillRect(QRect(x, y + 4, 12, 4), sparkle)


class PixelLoadingWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("pixel-loading")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 18)
        layout.setSpacing(4)
        layout.addStretch(1)
        self.dog = PixelDog()
        layout.addWidget(self.dog, 0, Qt.AlignmentFlag.AlignCenter)
        self.message = QLabel("知识打捞中.")
        self.message.setObjectName("pixel-message")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message)
        tip = QLabel("小狗正在把知识叼回来")
        tip.setObjectName("pixel-tip")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tip)
        mode = QLabel("WANXIANG // THINKING")
        mode.setObjectName("pixel-mode")
        mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mode)
        layout.addStretch(1)
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.setInterval(260)
        self.timer.timeout.connect(self.advance)
        self.timer.start()

    def advance(self) -> None:
        self.phase = (self.phase + 1) % 12
        self.dog.set_frame(self.phase)
        self.message.setText("知识打捞中" + "." * (self.phase % 3 + 1))


class LearningOverlay(QWidget):
    RESIZE_MARGIN = 10

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(360, 240)
        self.setMouseTracking(True)
        self.backdrop: QPixmap | None = None
        self.dark = True
        self.pixel = False
        self.dismissed = False
        self.user_adjusted = False
        self.press_position: QPoint | None = None
        self.press_geometry: QRect | None = None
        self.resize_edges: dict[str, bool] = {}
        self.root = QFrame(self)
        self.root.setObjectName("root")
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(22, 18, 22, 16)
        self.layout.setSpacing(11)
        self.header = QFrame()
        self.header.setObjectName("header")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel("万相 · 陪伴学习")
        self.title.setObjectName("title")
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        close = QPushButton("×")
        close.setObjectName("close")
        close.setToolTip("关闭")
        close.setFixedSize(28, 28)
        close.clicked.connect(self.close)
        header_layout.addWidget(self.title)
        header_layout.addWidget(close)
        self.layout.addWidget(self.header)
        self.header.installEventFilter(self)
        self.title.installEventFilter(self)
        self.context = QLabel("正在检查框内内容与上下文")
        self.context.setObjectName("context")
        self.context.setWordWrap(True)
        self.layout.addWidget(self.context)
        self.visual_surface = QFrame()
        self.visual_surface.setObjectName("visual")
        self.content = QVBoxLayout(self.visual_surface)
        self.content.setContentsMargins(9, 9, 9, 9)
        self.layout.addWidget(self.visual_surface, 1)
        self.visual_surface.hide()
        self.explanation = QLabel("正在理解…")
        self.explanation.setWordWrap(True)
        self.explanation.setObjectName("explanation")
        self.layout.addWidget(self.explanation)
        self.status = QLabel("")
        self.status.setObjectName("status")
        self.layout.addWidget(self.status)

    def set_theme(self, style: str) -> None:
        self.dark = style in DARK_STYLES
        self.pixel = style == "pixel"
        ink = "#f5ead7" if self.pixel else "#f3f7fc" if self.dark else "#172638"
        muted = "#aaa1c7" if self.pixel else "#b7c2d1" if self.dark else "#53667b"
        accent = "#ffd166" if self.pixel else "#9be5ff" if self.dark else "#075f82"
        surface = "rgba(39, 33, 71, 190)" if self.pixel else "rgba(255, 255, 255, 12)" if self.dark else "rgba(255, 255, 255, 72)"
        border = "rgba(255, 209, 102, 120)" if self.pixel else "rgba(255, 255, 255, 26)" if self.dark else "rgba(45, 76, 108, 22)"
        radius = 0 if self.pixel else 14
        border_width = 2 if self.pixel else 1
        pixel_css = """
            QFrame#pixel-loading { background: rgba(23, 21, 43, 150); border: 2px dashed #74689b; }
            QLabel#pixel-message { color: #ffd166; font-family: 'SFMono-Regular'; font-size: 20px; font-weight: 700; padding-top: 2px; }
            QLabel#pixel-tip { color: #f5ead7; font-size: 13px; font-weight: 600; }
            QLabel#pixel-mode { color: #58dfc0; font-family: 'SFMono-Regular'; font-size: 9px; padding-top: 7px; }
        """ if self.pixel else ""
        header_rule = "border-bottom: 2px solid rgba(255, 209, 102, 60); padding-bottom: 7px;" if self.pixel else ""
        self.root.setStyleSheet(f"""
            QFrame#root {{ background: transparent; }}
            QFrame#header {{ background: transparent; {header_rule} }}
            QFrame#visual {{ background: {surface}; border: {border_width}px solid {border}; border-radius: {radius}px; }}
            QLabel {{ color: {ink}; background: transparent; }}
            QLabel#title {{ font-size: 16px; font-weight: 700; }}
            QLabel#context {{ color: {accent}; font-size: 11px; }}
            QLabel#explanation {{ font-size: 14px; }}
            QLabel#status {{ color: {muted}; font-size: 10px; }}
            QPushButton#close {{ color: {ink}; background: rgba(255, 255, 255, 10); border: {border_width}px solid {border}; border-radius: {radius}px; font-size: 20px; }}
            QPushButton#close:hover {{ color: #17152b; background: {accent}; }}
            QWebEngineView {{ background: transparent; }}
            {pixel_css}
        """)

    def set_backdrop(self, screen, geometry: QRect) -> None:
        captured = capture_screen(screen, geometry)
        if not captured.isNull():
            backdrop = frosted_pixmap(captured)
            if self.pixel:
                ratio = backdrop.devicePixelRatio()
                original_size = backdrop.size()
                small = backdrop.scaled(
                    max(1, original_size.width() // 4),
                    max(1, original_size.height() // 4),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                backdrop = small.scaled(original_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                backdrop.setDevicePixelRatio(ratio)
            self.backdrop = backdrop

    def clear_content(self) -> None:
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.visual_surface.hide()

    def show_loading(self) -> None:
        self.dismissed = False
        self.user_adjusted = False
        self.set_theme("pixel")
        self.clear_content()
        self.title.setText("万相 · 像素学习舱")
        self.context.setText("INPUT RECEIVED // 正在读取框选内容")
        self.content.addWidget(PixelLoadingWidget(), 1)
        self.visual_surface.show()
        self.explanation.setText("先读懂框内内容，再挑选合适的图形。\n稍等一下，马上就好。")
        self.status.setText("标题栏拖动 · 边缘缩放 · Esc 关闭")

    def show_error(self, message: str) -> None:
        self.clear_content()
        self.title.setText("万相 · 暂时无法解释")
        self.context.setText("请检查后台服务、模型配置和系统权限")
        self.explanation.setText(message)
        self.status.setText("标题栏拖动 · 边缘缩放 · Esc 关闭")

    def show_learning(self, response: dict) -> None:
        artifact = response["artifact"]
        self.set_theme(artifact["style"])
        self.title.setText(artifact["title"])
        if artifact.get("context_used") is True:
            self.context.setText(f"已结合框外上下文 · {artifact.get('context_reason') or '补充了必要前文'}")
        elif artifact.get("context_used") is False:
            self.context.setText(f"框内信息足够 · {artifact.get('context_reason') or '无需扩展阅读'}")
        else:
            self.context.setText("智能上下文判断")
        self.clear_content()
        body = (artifact.get("html") or {}).get("body", "")
        document = (artifact.get("html") or {}).get("document", "")
        if document:
            view = QWebEngineView()
            view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
            view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
            view.page().setBackgroundColor(QColor(0, 0, 0, 0))
            view.setMinimumHeight(220)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            def fit_content(*_):
                def apply_zoom(dimensions):
                    if not isinstance(dimensions, list) or len(dimensions) != 2 or not all(dimensions):
                        return
                    zoom = min(1.0, (view.width() - 8) / dimensions[0], (view.height() - 8) / dimensions[1])
                    view.setZoomFactor(max(0.4, zoom))

                view.page().runJavaScript(
                    "[Math.max(document.body.scrollWidth,document.documentElement.scrollWidth),"
                    "Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)]",
                    apply_zoom,
                )

            view.loadFinished.connect(fit_content)
            view.setHtml(document)
            self.content.addWidget(view, 1)
            self.visual_surface.show()
            self.explanation.setText(artifact["explanation"])
        elif artifact.get("artifact_type") == "graph":
            graph = artifact["graph"]
            text = "\n".join(f"{node['label']}：{node['description']}" for node in graph["nodes"])
            self.explanation.setText(f"{text}\n\n{artifact['explanation']}")
        elif artifact.get("artifact_type") == "formula":
            formula = artifact["formula"]
            self.explanation.setText(f"{formula['latex']}\n\n{artifact['explanation']}")
        elif body:
            text = html.unescape(re.sub(r"<[^>]+>", " ", body))
            cleaned = re.sub(r"\s+", " ", text).strip()
            self.explanation.setText(f"{cleaned}\n\n{artifact['explanation']}")
        else:
            self.explanation.setText(artifact["explanation"])
        elapsed = artifact.get("timings_ms", {}).get("total")
        hint = f"标题栏拖动 · 边缘缩放 · {elapsed / 1000:.1f} 秒" if elapsed is not None else "标题栏拖动 · 边缘缩放 · Esc 关闭"
        self.status.setText(hint)

    def edges_at(self, position: QPoint) -> dict[str, bool]:
        rect = self.rect()
        return {
            "left": position.x() <= self.RESIZE_MARGIN,
            "right": position.x() >= rect.width() - self.RESIZE_MARGIN,
            "top": position.y() <= self.RESIZE_MARGIN,
            "bottom": position.y() >= rect.height() - self.RESIZE_MARGIN,
        }

    def update_resize_cursor(self, position: QPoint) -> None:
        edges = self.edges_at(position)
        horizontal = edges["left"] or edges["right"]
        vertical = edges["top"] or edges["bottom"]
        if horizontal and vertical:
            diagonal = (edges["left"] and edges["top"]) or (edges["right"] and edges["bottom"])
            cursor = Qt.CursorShape.SizeFDiagCursor if diagonal else Qt.CursorShape.SizeBDiagCursor
        elif horizontal:
            cursor = Qt.CursorShape.SizeHorCursor
        elif vertical:
            cursor = Qt.CursorShape.SizeVerCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)

    def begin_window_gesture(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        position = self.mapFromGlobal(event.globalPosition().toPoint())
        self.resize_edges = {edge: active for edge, active in self.edges_at(position).items() if active}
        self.press_position = event.globalPosition().toPoint()
        self.press_geometry = self.geometry()
        event.accept()
        return True

    def move_window_gesture(self, event) -> bool:
        if self.press_position is None or self.press_geometry is None:
            return False
        if not event.buttons() & Qt.MouseButton.LeftButton:
            self.end_window_gesture()
            return False
        delta = event.globalPosition().toPoint() - self.press_position
        if self.resize_edges:
            geometry = QRect(self.press_geometry)
            if self.resize_edges.get("left"):
                geometry.setLeft(min(geometry.left() + delta.x(), geometry.right() - self.minimumWidth() + 1))
            if self.resize_edges.get("right"):
                geometry.setRight(max(geometry.right() + delta.x(), geometry.left() + self.minimumWidth() - 1))
            if self.resize_edges.get("top"):
                geometry.setTop(min(geometry.top() + delta.y(), geometry.bottom() - self.minimumHeight() + 1))
            if self.resize_edges.get("bottom"):
                geometry.setBottom(max(geometry.bottom() + delta.y(), geometry.top() + self.minimumHeight() - 1))
            self.setGeometry(geometry)
        else:
            self.move(self.press_geometry.topLeft() + delta)
        self.user_adjusted = True
        event.accept()
        return True

    def end_window_gesture(self) -> None:
        self.press_position = None
        self.press_geometry = None
        self.resize_edges = {}
        self.unsetCursor()

    def eventFilter(self, watched, event) -> bool:
        if watched in (self.header, self.title):
            if event.type() == event.Type.MouseButtonPress:
                return self.begin_window_gesture(event)
            if event.type() == event.Type.MouseMove and self.move_window_gesture(event):
                return True
            if event.type() == event.Type.MouseButtonRelease and self.press_position is not None:
                self.end_window_gesture()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        if not self.begin_window_gesture(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self.move_window_gesture(event):
            self.update_resize_cursor(event.position().toPoint())
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.end_window_gesture()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if self.press_position is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = QRectF(self.rect()).adjusted(14, 12, -14, -18)
        if self.pixel:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            step = 10
            path = QPainterPath()
            path.moveTo(surface.left() + step, surface.top())
            path.lineTo(surface.right() - step, surface.top())
            path.lineTo(surface.right() - step, surface.top() + 4)
            path.lineTo(surface.right(), surface.top() + 4)
            path.lineTo(surface.right(), surface.bottom() - step)
            path.lineTo(surface.right() - 4, surface.bottom() - step)
            path.lineTo(surface.right() - 4, surface.bottom() - 4)
            path.lineTo(surface.right() - step, surface.bottom() - 4)
            path.lineTo(surface.right() - step, surface.bottom())
            path.lineTo(surface.left() + step, surface.bottom())
            path.lineTo(surface.left() + step, surface.bottom() - 4)
            path.lineTo(surface.left() + 4, surface.bottom() - 4)
            path.lineTo(surface.left() + 4, surface.bottom() - step)
            path.lineTo(surface.left(), surface.bottom() - step)
            path.lineTo(surface.left(), surface.top() + step)
            path.lineTo(surface.left() + 4, surface.top() + step)
            path.lineTo(surface.left() + 4, surface.top() + 4)
            path.lineTo(surface.left() + step, surface.top() + 4)
            path.closeSubpath()
            painter.fillRect(surface.translated(6, 7), QColor(8, 7, 17, 220))
            painter.setClipPath(path)
            if self.backdrop and not self.backdrop.isNull():
                painter.drawPixmap(self.rect(), self.backdrop)
            else:
                painter.fillRect(self.rect(), QColor(23, 21, 43, 235))
            painter.fillRect(self.rect(), QColor(23, 21, 43, 205))
            grid_pen = QPen(QColor(170, 161, 199, 14), 1)
            painter.setPen(grid_pen)
            for x in range(int(surface.left()), int(surface.right()), 8):
                painter.drawLine(x, int(surface.top()), x, int(surface.bottom()))
            for y in range(int(surface.top()), int(surface.bottom()), 8):
                painter.drawLine(int(surface.left()), y, int(surface.right()), y)
            painter.setClipping(False)
            painter.setPen(QPen(QColor(8, 7, 17), 5))
            painter.drawPath(path)
            painter.setPen(QPen(QColor("#ffd166"), 2))
            painter.drawPath(path)
            painter.fillRect(QRectF(surface.left() + 16, surface.top() - 1, 34, 3), QColor("#58dfc0"))
            painter.fillRect(QRectF(surface.right() - 50, surface.bottom() - 1, 34, 3), QColor("#58dfc0"))
            return
        for spread, alpha, offset in ((8, 10, 13), (4, 16, 9), (0, 28, 4)):
            shadow = QPainterPath()
            shadow.addRoundedRect(surface.adjusted(-spread, -spread, spread, spread), 22 + spread, 22 + spread)
            painter.fillPath(shadow.translated(0, offset), QColor(2, 8, 18, alpha))
        path = QPainterPath()
        path.addRoundedRect(surface, 22, 22)
        painter.setClipPath(path)
        if self.backdrop and not self.backdrop.isNull():
            painter.drawPixmap(self.rect(), self.backdrop)
        else:
            painter.fillRect(self.rect(), QColor(20, 28, 40, 190))
        painter.fillRect(self.rect(), QColor(12, 20, 32, 192) if self.dark else QColor(239, 245, 250, 205))
        sheen = QLinearGradient(surface.topLeft(), surface.bottomLeft())
        sheen.setColorAt(0, QColor(255, 255, 255, 28 if self.dark else 80))
        sheen.setColorAt(0.45, QColor(255, 255, 255, 9 if self.dark else 28))
        sheen.setColorAt(1, QColor(255, 255, 255, 3 if self.dark else 10))
        painter.fillRect(surface, sheen)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 105) if self.dark else QColor(255, 255, 255, 185), 1))
        painter.drawPath(path)
        accent = QLinearGradient(surface.topLeft(), surface.topRight())
        accent.setColorAt(0, QColor(109, 222, 255, 0))
        accent.setColorAt(0.22, QColor(109, 222, 255, 150))
        accent.setColorAt(0.65, QColor(183, 157, 255, 105))
        accent.setColorAt(1, QColor(183, 157, 255, 0))
        painter.setPen(QPen(accent, 1.2))
        painter.drawLine(surface.topLeft() + QPoint(24, 1), surface.topRight() - QPoint(24, -1))

    def resizeEvent(self, event) -> None:
        self.root.setGeometry(self.rect().adjusted(14, 12, -14, -18))
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.dismissed = True
        self.end_window_gesture()
        super().closeEvent(event)


class CompanionController(QObject):
    result_ready = Signal(object)
    error_ready = Signal(str)

    def __init__(self, url: str, context_interval: int, style: str):
        super().__init__()
        self.url = url
        self.style = style
        self.reader = StaticSnapshotReader(context_interval * 1000)
        self.selection_overlay = SelectionOverlay()
        self.overlay = LearningOverlay()
        self.bridge = InputBridge()
        self.bridge.activated.connect(self.on_activate)
        self.bridge.cancelled.connect(self.on_cancel)
        self.bridge.pressed.connect(self.on_pressed)
        self.bridge.moved.connect(self.on_moved)
        self.bridge.released.connect(self.on_released)
        self.result_ready.connect(self.show_result)
        self.error_ready.connect(self.show_error)
        self.start: QPoint | None = None
        self.selection_source: QPixmap | None = None
        self.armed = False
        self.selecting = False
        self.busy = False
        self.cursor_override = False
        self.web_engine_warmup = QWebEngineView()
        self.web_engine_warmup.setHtml("<!doctype html><html><body></body></html>")
        self.native_keys = None
        self.keys = None
        if sys.platform == "darwin":
            self.native_keys = MacKeyboardListener(self.bridge.activated.emit, self.bridge.cancelled.emit)
            self.native_keys.start()
        else:
            self.pressed_keys: set[object] = set()
            self.shortcut_down = False
            self.keys = keyboard.Listener(on_press=self.on_global_key_press, on_release=self.on_global_key_release)
            self.keys.start()
        self.listener = mouse.Listener(on_click=self.on_global_click, on_move=self.on_global_move)
        self.listener.start()
        self.reader.start()

    def on_global_key_press(self, key) -> None:
        key = self.keys.canonical(key)
        if key == keyboard.Key.esc:
            self.bridge.cancelled.emit()
            return
        self.pressed_keys.add(key)
        char = getattr(key, "char", None)
        if not char or char.lower() != "x" or self.shortcut_down:
            return
        shift = any(modifier in self.pressed_keys for modifier in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r))
        control = any(modifier in self.pressed_keys for modifier in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r))
        if shift and control:
            self.shortcut_down = True
            self.bridge.activated.emit()

    def on_global_key_release(self, key) -> None:
        key = self.keys.canonical(key)
        char = getattr(key, "char", None)
        if char and char.lower() == "x":
            self.shortcut_down = False
        self.pressed_keys.discard(key)

    def on_global_click(self, x, y, button, pressed) -> None:
        if button != mouse.Button.left:
            return
        if pressed and self.armed:
            self.bridge.pressed.emit((x, y))
        elif not pressed and self.selecting:
            self.bridge.released.emit((x, y))

    def on_global_move(self, x, y) -> None:
        if self.selecting:
            self.bridge.moved.emit((x, y))

    def set_cross_cursor(self, enabled: bool) -> None:
        if enabled and not self.cursor_override:
            QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
            self.cursor_override = True
        elif not enabled and self.cursor_override:
            QApplication.restoreOverrideCursor()
            self.cursor_override = False

    def on_activate(self) -> None:
        if self.busy:
            return
        if self.armed or self.selecting:
            self.cancel_selection()
            return
        self.armed = True
        self.reader.suspended = True
        self.set_cross_cursor(True)
        print("万相框选已就绪：按住左键拖动，Esc 取消", flush=True)

    def cancel_selection(self) -> None:
        self.armed = False
        self.selecting = False
        self.start = None
        self.selection_source = None
        self.selection_overlay.hide()
        self.reader.suspended = self.busy
        self.set_cross_cursor(False)

    def on_cancel(self) -> None:
        if self.armed or self.selecting:
            self.cancel_selection()
        else:
            self.overlay.close()

    def on_pressed(self, position) -> None:
        if self.busy or not self.armed:
            return
        self.armed = False
        self.start = QPoint(round(position[0]), round(position[1]))
        self.selecting = True
        screen = QApplication.screenAt(self.start) or QApplication.primaryScreen()
        self.selection_source = capture_screen(screen)
        self.selection_overlay.begin(self.start, screen)

    def on_moved(self, position) -> None:
        if self.selecting:
            self.selection_overlay.update_position(QPoint(round(position[0]), round(position[1])))

    def on_released(self, position) -> None:
        if not self.selecting or not self.start:
            return
        self.selecting = False
        self.selection_overlay.hide()
        self.set_cross_cursor(False)
        end = QPoint(round(position[0]), round(position[1]))
        rect = QRect(self.start, end).normalized()
        self.start = None
        if rect.width() < 12 or rect.height() < 12:
            self.selection_source = None
            self.reader.suspended = False
            return
        screen = QApplication.screenAt(rect.center()) or QApplication.primaryScreen()
        print(f"万相框选：{rect.width()}×{rect.height()}，开始陪伴学习", flush=True)
        self.start_learning(rect, screen)

    def loading_geometry(self, selection: QRect, screen) -> QRect:
        width = min(max(selection.width(), 420), int(screen.geometry().width() * 0.9))
        height = min(max(selection.height(), 220), int(screen.geometry().height() * 0.85))
        geometry = QRect(selection.center().x() - width // 2, selection.center().y() - height // 2, width, height)
        geometry.moveLeft(min(max(geometry.x(), screen.geometry().x() + 12), screen.geometry().right() - width - 10))
        geometry.moveTop(min(max(geometry.y(), screen.geometry().y() + 12), screen.geometry().bottom() - height - 10))
        return geometry

    def start_learning(self, selection: QRect, screen) -> None:
        self.busy = True
        if self.selection_source and not self.selection_source.isNull():
            ratio = self.selection_source.devicePixelRatio()
            screen_geometry = screen.geometry()
            selected = self.selection_source.copy(
                round((selection.x() - screen_geometry.x()) * ratio),
                round((selection.y() - screen_geometry.y()) * ratio),
                round(selection.width() * ratio),
                round(selection.height() * ratio),
            )
            selected.setDevicePixelRatio(ratio)
        else:
            selected = capture_screen(screen, selection)
        self.selection_source = None
        context = self.reader.latest(screen)
        if selected.isNull():
            self.reader.suspended = False
            self.busy = False
            self.error_ready.emit("无法读取框选画面。请检查屏幕录制权限后重试。")
            return
        self.overlay.show_loading()
        geometry = self.loading_geometry(selection, screen)
        self.overlay.setGeometry(geometry)
        self.overlay.set_backdrop(screen, geometry)
        self.overlay.show()
        self.overlay.raise_()
        screen_geometry = screen.geometry()
        payload = {
            "image_base64": encode_pixmap(selected),
            "context_image_base64": encode_pixmap(context, "JPG", 1600) if context and not context.isNull() else None,
            "context_mode": "auto" if context else "never",
            "context_text": "快照来自框选前的常态静态读取，仅在框内信息不足时使用。",
            "preference": "auto",
            "style": self.style,
            "source": "companion-static-screen-snapshot",
            "selection": {
                "x": selection.x(), "y": selection.y(), "width": selection.width(), "height": selection.height(),
                "screen_x": screen_geometry.x(), "screen_y": screen_geometry.y(),
                "screen_width": screen_geometry.width(), "screen_height": screen_geometry.height(),
            },
        }
        threading.Thread(target=self.request_learning, args=(payload,), daemon=True).start()

    def request_learning(self, payload: dict) -> None:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=150) as response:
                self.result_ready.emit(json.loads(response.read()))
        except urllib.error.HTTPError as error:
            try:
                detail = json.loads(error.read()).get("detail", str(error))
            except Exception:
                detail = str(error)
            self.error_ready.emit(detail)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            self.error_ready.emit(f"无法连接万相学习服务：{error}")

    def show_result(self, response: dict) -> None:
        self.busy = False
        self.reader.suspended = False
        if self.overlay.dismissed:
            return
        if not self.overlay.user_adjusted:
            geometry = response["overlay"]
            self.overlay.setGeometry(QRect(geometry["x"], geometry["y"], geometry["width"], geometry["height"]))
        self.overlay.show_learning(response)
        self.overlay.show()
        self.overlay.raise_()

    def show_error(self, message: str) -> None:
        self.busy = False
        self.reader.suspended = False
        if self.overlay.dismissed:
            return
        self.overlay.show_error(message)
        self.overlay.show()


def main() -> int:
    parser = argparse.ArgumentParser(description="万相陪伴学习浮层")
    parser.add_argument("--url", default="http://127.0.0.1:8765/v2/learning")
    parser.add_argument("--context-interval", type=int, default=5)
    parser.add_argument("--style", default="pixel")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        status = permission_status()
        print(json.dumps(status, ensure_ascii=False))
        return 0 if status["screen"] else 2
    if sys.platform == "darwin":
        status = permission_status()
        if not status["screen"]:
            import Quartz
            Quartz.CGRequestScreenCaptureAccess()
            print("请在 macOS 系统设置 → 隐私与安全性 → 屏幕录制中允许 Python/终端，然后重启 companion。", file=sys.stderr)
            return 2
        if not status["input"]:
            print("提示：全局快捷键监听可能还需要辅助功能或输入监控权限。", file=sys.stderr)
        try:
            from AppKit import NSApplication
            NSApplication.sharedApplication().setActivationPolicy_(1)
        except ImportError:
            pass
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    controller = CompanionController(args.url, args.context_interval, args.style)
    shortcut = "⌘⇧X 或 Ctrl+Shift+X" if sys.platform == "darwin" else "Ctrl+Shift+X"
    print(f"万相陪伴学习已启动：按 {shortcut} 后左键拖动框选，Esc 取消或关闭；静态快照每 {args.context_interval} 秒读取且仅保存在内存。")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
