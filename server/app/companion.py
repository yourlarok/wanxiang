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

from pynput import mouse
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


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


class MouseBridge(QObject):
    pressed = Signal(object)
    moved = Signal(object)
    released = Signal(object)


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


class LearningOverlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.backdrop: QPixmap | None = None
        self.dark = True
        self.root = QFrame(self)
        self.root.setObjectName("root")
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(18, 14, 18, 16)
        self.layout.setSpacing(10)
        header = QHBoxLayout()
        self.title = QLabel("万相 · 陪伴学习")
        self.title.setObjectName("title")
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        close = QPushButton("×")
        close.setObjectName("close")
        close.setFixedSize(30, 30)
        close.clicked.connect(self.hide)
        header.addWidget(self.title)
        header.addWidget(close)
        self.layout.addLayout(header)
        self.context = QLabel("正在检查框内内容与上下文")
        self.context.setObjectName("context")
        self.layout.addWidget(self.context)
        self.content = QVBoxLayout()
        self.layout.addLayout(self.content, 1)
        self.explanation = QLabel("正在理解…")
        self.explanation.setWordWrap(True)
        self.explanation.setObjectName("explanation")
        self.layout.addWidget(self.explanation)
        self.status = QLabel("")
        self.status.setObjectName("status")
        self.layout.addWidget(self.status)

    def set_theme(self, style: str) -> None:
        self.dark = style in DARK_STYLES
        ink = "#edf3fb" if self.dark else "#253247"
        muted = "#b0bdcf" if self.dark else "#637086"
        accent = "#80d7ff" if self.dark else "#167ca8"
        self.root.setStyleSheet(f"""
            QFrame#root {{ background: transparent; }}
            QLabel {{ color: {ink}; background: transparent; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
            QLabel#title {{ font-size: 16px; font-weight: 700; }}
            QLabel#context {{ color: {accent}; font-size: 11px; }}
            QLabel#explanation {{ font-size: 14px; line-height: 1.55; }}
            QLabel#status {{ color: {muted}; font-size: 10px; }}
            QPushButton#close {{ color: {ink}; background: transparent; border: 0; border-radius: 15px; font-size: 22px; }}
            QPushButton#close:hover {{ background: #88888844; }}
            QSvgWidget {{ background: transparent; }}
        """)

    def set_backdrop(self, screen, geometry: QRect) -> None:
        captured = capture_screen(screen, geometry)
        if not captured.isNull():
            small = captured.scaled(max(1, geometry.width() // 16), max(1, geometry.height() // 16), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.backdrop = small.scaled(geometry.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def clear_content(self) -> None:
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_loading(self) -> None:
        self.set_theme("textbook")
        self.title.setText("万相 · 正在理解")
        self.context.setText("检查框内内容 · 判断是否需要框外上下文")
        self.explanation.setText("正在生成结合当前内容的学习解释…")
        self.status.setText("Esc 关闭")

    def show_error(self, message: str) -> None:
        self.title.setText("万相 · 暂时无法解释")
        self.context.setText("请检查后台服务、模型配置和系统权限")
        self.explanation.setText(message)
        self.status.setText("Esc 关闭")

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
        match = re.search(r"<svg\b[\s\S]*</svg>", body)
        if match:
            svg = QSvgWidget()
            svg.load(QByteArray(match.group(0).encode("utf-8")))
            svg.setMinimumHeight(180)
            svg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.content.addWidget(svg, 1)
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
        if match:
            self.explanation.setText(artifact["explanation"])
        elapsed = artifact.get("timings_ms", {}).get("total")
        self.status.setText(f"Esc 关闭 · {elapsed / 1000:.1f} 秒" if elapsed is not None else "Esc 关闭")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 18, 18)
        painter.setClipPath(path)
        if self.backdrop and not self.backdrop.isNull():
            painter.drawPixmap(self.rect(), self.backdrop)
        painter.fillRect(self.rect(), QColor(14, 20, 31, 218) if self.dark else QColor(248, 250, 253, 218))
        painter.setPen(QPen(QColor(255, 255, 255, 65) if self.dark else QColor(60, 80, 110, 45), 1))
        painter.drawPath(path)

    def resizeEvent(self, event) -> None:
        self.root.setGeometry(self.rect())
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class CompanionController(QObject):
    result_ready = Signal(object)
    error_ready = Signal(str)

    def __init__(self, url: str, context_interval: int, style: str):
        super().__init__()
        self.url = url
        self.style = style
        self.reader = StaticSnapshotReader(context_interval * 1000)
        self.selection_overlay = SelectionOverlay()
        self.overlay: LearningOverlay | None = None
        self.bridge = MouseBridge()
        self.bridge.pressed.connect(self.on_pressed)
        self.bridge.moved.connect(self.on_moved)
        self.bridge.released.connect(self.on_released)
        self.result_ready.connect(self.show_result)
        self.error_ready.connect(self.show_error)
        self.start: QPoint | None = None
        self.selection_source: QPixmap | None = None
        self.selecting = False
        self.busy = False
        self.listener = mouse.Listener(on_click=self.on_global_click, on_move=self.on_global_move)
        self.listener.start()
        self.reader.start()

    def on_global_click(self, x, y, button, pressed) -> None:
        if button != mouse.Button.right:
            return
        if pressed:
            self.bridge.pressed.emit((x, y))
        else:
            self.bridge.released.emit((x, y))

    def on_global_move(self, x, y) -> None:
        if self.selecting:
            self.bridge.moved.emit((x, y))

    def on_pressed(self, position) -> None:
        if self.busy:
            return
        self.start = QPoint(round(position[0]), round(position[1]))
        self.selecting = True
        self.reader.suspended = True
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
        end = QPoint(round(position[0]), round(position[1]))
        rect = QRect(self.start, end).normalized()
        self.start = None
        if rect.width() < 12 or rect.height() < 12:
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
        self.overlay = LearningOverlay()
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

    def positioned_overlay(self, geometry: dict, screen) -> LearningOverlay:
        if self.overlay:
            self.overlay.hide()
        self.overlay = LearningOverlay()
        rect = QRect(geometry["x"], geometry["y"], geometry["width"], geometry["height"])
        self.overlay.setGeometry(rect)
        self.overlay.set_backdrop(screen, rect)
        return self.overlay

    def show_result(self, response: dict) -> None:
        screen = QApplication.screenAt(QPoint(response["overlay"]["x"], response["overlay"]["y"])) or QApplication.primaryScreen()
        overlay = self.positioned_overlay(response["overlay"], screen)
        overlay.show_learning(response)
        overlay.show()
        overlay.raise_()
        self.busy = False
        self.reader.suspended = False

    def show_error(self, message: str) -> None:
        if self.overlay:
            self.overlay.show_error(message)
            self.overlay.show()
        self.busy = False
        self.reader.suspended = False


def main() -> int:
    parser = argparse.ArgumentParser(description="万相陪伴学习浮层")
    parser.add_argument("--url", default="http://127.0.0.1:8765/v2/learning")
    parser.add_argument("--context-interval", type=int, default=5)
    parser.add_argument("--style", default="textbook")
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
            print("提示：全局右键监听可能还需要辅助功能或输入监控权限。", file=sys.stderr)
        try:
            from AppKit import NSApplication
            NSApplication.sharedApplication().setActivationPolicy_(1)
        except ImportError:
            pass
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    controller = CompanionController(args.url, args.context_interval, args.style)
    print(f"万相陪伴学习已启动：右键拖动框选，Esc 关闭浮层；静态快照每 {args.context_interval} 秒读取且仅保存在内存。")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
