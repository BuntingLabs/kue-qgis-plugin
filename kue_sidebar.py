# Copyright Bunting Labs, Inc. 2024

from PyQt5.QtWidgets import (
    QDockWidget,
    QStackedWidget,
    QWidget,
    QApplication,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QFrame,
    QListWidgetItem,
    QLabel,
    QTextEdit,
    QCheckBox,
    QToolButton,
)
from PyQt5.QtGui import QTextCursor, QFont, QColor, QDesktopServices
from PyQt5.QtCore import Qt, QSettings, QTimer
from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject
from qgis.core import QgsIconUtils

from typing import Callable
import os
import re
from .kue_find import KueFind, VECTOR_EXTENSIONS, RASTER_EXTENSIONS
from .kue_messages import (
    KUE_FIND_FILTER_EXPLANATION,
    KUE_CLEAR_CHAT,
    KUE_DESCRIPTION,
    KUE_SUBSCRIPTION,
    KUE_LOGIN_BUTTON,
    KueResponseStatus,
    status_to_color,
)


class KueSidebar(QDockWidget):
    def __init__(
        self,
        iface,
        messageSent: Callable,
        authenticateUser: Callable,
        kue_find: KueFind,
        ask_kue_message: str,
        lang: str,
        setChatMessageID: Callable,
        starter_messages: list[str],
    ):
        super().__init__("Kue AI", iface.mainWindow())

        # Properties
        self.iface = iface
        self.messageSent = messageSent
        self.authenticateUser = authenticateUser
        self.kue_find = kue_find
        self.lang = lang
        self.setChatMessageID = setChatMessageID
        self.starter_messages = starter_messages
        # The parent widget is either kue or auth
        self.parent_widget = QStackedWidget()

        # Connect to map canvas extent changes
        self.iface.mapCanvas().extentsChanged.connect(self.maybeUpdateFindResults)
        # Also update when indexing is done, regardless of bbox checkbox
        self.kue_find.filesIndexed.connect(
            lambda cnt: self.maybeUpdateFindResults(only_for_bbox=False)
        )

        # Add auth widget
        self.auth_widget = QWidget()
        auth_layout = QVBoxLayout()
        auth_layout.setAlignment(Qt.AlignVCenter)

        title = QLabel("<h2>Kue</h2>")
        title.setContentsMargins(0, 0, 0, 10)

        description = QLabel(KUE_DESCRIPTION.get(lang, KUE_DESCRIPTION["en"]))
        description.setWordWrap(True)
        description.setContentsMargins(0, 0, 0, 10)
        description.setMinimumWidth(300)

        pricing = QLabel(KUE_SUBSCRIPTION.get(lang, KUE_SUBSCRIPTION["en"]))
        pricing.setWordWrap(True)
        pricing.setContentsMargins(0, 0, 0, 10)
        pricing.setMinimumWidth(300)

        login_button = QPushButton(KUE_LOGIN_BUTTON.get(lang, KUE_LOGIN_BUTTON["en"]))
        login_button.setFixedWidth(280)
        login_button.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; border: none; padding: 8px; border-radius: 4px; } QPushButton:hover { background-color: #0b5ed7; }"
        )
        login_button.clicked.connect(self.authenticateUser)

        auth_layout.addWidget(title)
        auth_layout.addWidget(description)
        auth_layout.addWidget(pricing)
        auth_layout.addWidget(login_button)
        self.auth_widget.setLayout(auth_layout)

        # 1. Build the textbox and enter button widget
        self.message_bar_widget = QWidget()

        self.textbox = QTextEdit()
        self.textbox.setFixedHeight(50)
        self.textbox.setAcceptRichText(False)
        self.textbox.setPlaceholderText(ask_kue_message)
        self.textbox.textChanged.connect(
            lambda: self.onTextUpdate(self.textbox.toPlainText())
        )

        def handleKeyPress(e):
            if e.key() == Qt.Key_Return:
                self.onEnterClicked()
            else:
                QTextEdit.keyPressEvent(self.textbox, e)

        self.textbox.keyPressEvent = handleKeyPress

        self.enter_button = QPushButton("Enter")
        self.enter_button.setFixedSize(50, 20)
        self.enter_button.clicked.connect(self.onEnterClicked)

        # Chatbox and button at bottom
        self.h_layout = QHBoxLayout()
        self.h_layout.addWidget(self.textbox)
        self.h_layout.addWidget(self.enter_button)
        self.message_bar_widget.setLayout(self.h_layout)

        # 2. Build the parent for both kue and find
        self.above_mb_widget = QStackedWidget()

        # Build kue widget
        self.kue_widget = QWidget()

        self.chat_display = TextEditWithButtons()
        # self.chat_display.setReadOnly(True)
        self.chat_display.sidebar_parent = self
        self.chat_display.setFrameShape(QFrame.NoFrame)
        self.chat_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.kue_layout = QVBoxLayout()
        self.kue_layout.setContentsMargins(0, 0, 0, 0)
        self.kue_layout.addWidget(self.chat_display)
        self.kue_widget.setLayout(self.kue_layout)

        self.find_widget = QWidget()
        self.find_layout = QVBoxLayout()
        self.find_layout.setContentsMargins(0, 0, 0, 0)

        # Add checkbox above results
        translated_explanation = KUE_FIND_FILTER_EXPLANATION.get(
            lang, KUE_FIND_FILTER_EXPLANATION["en"]
        )
        self.map_canvas_filter = QCheckBox(translated_explanation)
        self.find_layout.addWidget(self.map_canvas_filter)

        self.find_results = FileListWidget()
        self.find_results.setWordWrap(True)
        self.find_results.setFrameShape(QFrame.NoFrame)
        self.find_results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.find_results.setTextElideMode(Qt.ElideNone)
        self.find_results.setDragEnabled(True)
        self.find_results.setDragDropMode(QListWidget.DragOnly)

        # Handle opening a file
        delegate = KueFileResult()
        delegate.open_raster = self.openRasterFile
        delegate.open_vector = self.openVectorFile
        self.find_results.setItemDelegate(delegate)

        self.find_layout.addWidget(self.find_results)
        self.find_widget.setLayout(self.find_layout)

        self.above_mb_widget.addWidget(self.kue_widget)
        self.above_mb_widget.addWidget(self.find_widget)
        self.above_mb_widget.setCurrentIndex(0)

        # Create a layout for kue (kue chat + find)
        self.chat_layout = QVBoxLayout()

        self.chat_layout.addWidget(self.above_mb_widget, 1)
        self.chat_layout.addWidget(self.message_bar_widget, 0)

        # Add message bar widget to parent widget
        self.kue_widget = QWidget()
        self.kue_widget.setLayout(self.chat_layout)
        self.parent_widget.addWidget(self.kue_widget)
        self.parent_widget.addWidget(self.auth_widget)

        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(8, 0, 8, 0)

        title_label = QLabel("Kue AI")

        self.reset_chat_btn = QPushButton(
            KUE_CLEAR_CHAT.get(lang, KUE_CLEAR_CHAT["en"])
        )
        self.reset_chat_btn.clicked.connect(self.reset)
        self.reset_chat_btn.setFixedWidth(80)
        self.reset_chat_btn.setToolTip("Creates a new conversation")

        # Standard controls

        self.float_button = QToolButton(self)
        float_icon = self.style().standardIcon(QStyle.SP_TitleBarNormalButton)
        self.float_button.setIcon(float_icon)
        self.float_button.clicked.connect(
            lambda: self.setFloating(not self.isFloating())
        )
        self.float_button.setToolTip("Detach chat window")

        self.close_button = QToolButton(self)
        close_icon = self.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        self.close_button.setIcon(close_icon)
        self.close_button.clicked.connect(self.close)
        self.close_button.setToolTip("Close chat window")

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.reset_chat_btn)
        # standard
        title_layout.addWidget(self.float_button)
        title_layout.addWidget(self.close_button)

        self.setTitleBarWidget(title_widget)

        self.parent_widget.setCurrentIndex(
            0 if QSettings().value("buntinglabs-kue/auth_token") else 1
        )

        self.setWidget(self.parent_widget)

        # Set up a timer to poll the QSettings value
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.checkAuthToken)
        self.poll_timer.start(5000)  # 5 seconds

        for msg in self.starter_messages:
            self.addMessage({"role": "assistant", "msg": msg})

    def checkAuthToken(self):
        # Check if the auth token is set and update the widget index accordingly
        if QSettings().value("buntinglabs-kue/auth_token"):
            self.parent_widget.setCurrentIndex(0)
        else:
            self.parent_widget.setCurrentIndex(1)

    def addAction(self, action):
        if action.get("kue_action_svg"):
            assert "message" in action

            self.resetTextCursor()
            cursor = self.chat_display.textCursor()
            while True:
                cursor.movePosition(cursor.Left, cursor.KeepAnchor)
                if cursor.selectedText() != "\u2029":
                    cursor.movePosition(cursor.Right)
                    break
                cursor.removeSelectedText()
            self.resetTextCursor()
            self.chat_display.append("")

            self.chat_display.setAlignment(Qt.AlignLeft)
            color = status_to_color(action["status"])
            self.chat_display.insertHtml(f"""<div style="margin: 8px;">
                    <img src="{action["kue_action_svg"]}" width="16" height="16" style="vertical-align: middle"/>
                    <span style="color: {color};">{action["message"]}</span>
                </div>""")
            self.chat_display.append("")
            self.chat_display.verticalScrollBar().setValue(
                self.chat_display.verticalScrollBar().maximum()
            )

    def addMessage(self, msg):
        # Super simple markdown formatting
        msg["msg"] = msg["msg"].replace("\n", "<br>")
        msg["msg"] = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", msg["msg"])
        msg["msg"] = re.sub(r"\*(.*?)\*", r"<i>\1</i>", msg["msg"])

        # Format message based on role
        if msg["role"] == "user":
            html = f'<div style="text-align: right; margin: 8px;">{msg["msg"]}</div>'
        elif msg["role"] == "error":
            html = f'<div style="text-align: left; margin: 8px; color: red;">{msg["msg"]}</div>'
        elif msg["role"] == "geoprocessing":
            html = f"""
                <div style="margin: 8px;">
                    <img src=":/images/themes/default/processingAlgorithm.svg" width="16" height="16" style="vertical-align: middle"/>
                    <span>{msg["msg"]}</span>
                </div>
            """
        else:
            html = f'<div style="text-align: left; margin: 8px;">{msg["msg"]}</div>'

        # Add run code button if needed
        if msg.get("has_button"):
            html += f"""
                <div style="text-align: right;">
                    <button onclick="runCode('{msg["msg"]}')" 
                            style="background: #eee; border: 1px solid #ccc; padding: 4px 8px;">
                        Run Code
                    </button>
                </div>
            """

        # Append and scroll to bottom
        self.resetTextCursor()
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.Left, cursor.KeepAnchor)
        if cursor.selectedText() == "\u2029":
            cursor.removeSelectedText()

        self.chat_display.append("")
        self.chat_display.setAlignment(
            Qt.AlignRight if msg["role"] == "user" else Qt.AlignLeft
        )
        self.chat_display.insertHtml(html)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def addError(self, msg: str):
        self.insertChars(msg, QColor("red"))

    def insertChars(self, chars, start_color=None):
        self.chat_display.moveCursor(QTextCursor.End)
        if start_color:
            ccf = self.chat_display.currentCharFormat()
            ccf.setForeground(start_color)
            self.chat_display.setCurrentCharFormat(ccf)
        chars = chars.replace("\n\n", "\n")
        while chars:
            # Find first special marker (*, ** or markdown link)
            link_match = re.search(r"\[(.*?)\]\((.*?)\)", chars)
            link_pos = link_match.start() if link_match else -1
            marker_pos = min(
                (chars.find(x) for x in ["*", "**"] if x in chars), default=-1
            )

            # Handle text before any markers
            first_marker = (
                min(p for p in [marker_pos, link_pos] if p != -1)
                if marker_pos != -1 or link_pos != -1
                else -1
            )
            if first_marker == -1:
                self.chat_display.insertPlainText(chars)
                break
            elif first_marker > 0:
                self.chat_display.insertPlainText(chars[:first_marker])
                chars = chars[first_marker:]
                continue

            # Handle markdown link
            if link_match and link_pos == 0:
                text, url = link_match.groups()
                # Set link blue, underlined, then revert back to original color
                ccf = self.chat_display.currentCharFormat()
                current_foreground = ccf.foreground().color()
                ccf.setForeground(QColor("blue"))
                ccf.setAnchor(True)
                ccf.setAnchorHref(url)
                ccf.setToolTip(url)
                ccf.setFontUnderline(True)
                self.chat_display.setCurrentCharFormat(ccf)
                self.chat_display.insertPlainText(text)
                ccf = self.chat_display.currentCharFormat()
                ccf.setForeground(current_foreground)
                ccf.setAnchor(False)
                ccf.setAnchorHref("")
                ccf.setToolTip("")
                ccf.setFontUnderline(False)
                self.chat_display.setCurrentCharFormat(ccf)
                chars = chars[link_match.end() :]
            # Handle formatting markers
            elif chars.startswith("**"):
                ccf = self.chat_display.currentCharFormat()
                ccf.setFontWeight(
                    QFont.Bold if ccf.fontWeight() == QFont.Normal else QFont.Normal
                )
                self.chat_display.setCurrentCharFormat(ccf)
                chars = chars[2:]
            elif chars.startswith("*"):
                ccf = self.chat_display.currentCharFormat()
                ccf.setFontItalic(not ccf.fontItalic())
                self.chat_display.setCurrentCharFormat(ccf)
                chars = chars[1:]
        if start_color:
            end_color = self.palette().color(self.palette().Text)
            ccf.setForeground(end_color)
            self.chat_display.setCurrentCharFormat(ccf)

    def resetTextCursor(self):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_display.setTextCursor(cursor)

    def onChatButtonClicked(self, msg):
        # Handle button click
        from console import console
        from PyQt5.QtWidgets import QApplication

        self.iface.actionShowPythonDialog().trigger()
        console._console.console.toggleEditor(True)

        QApplication.clipboard().setText(msg["msg"])
        console._console.console.pasteEditor()

    def appendHtmlToBottom(self, html, break_line=True):
        # Append and scroll to bottom
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_display.setTextCursor(cursor)

        if break_line:
            self.chat_display.append("")
        self.chat_display.insertHtml(html)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def onEnterClicked(self):
        if self.textbox.toPlainText().startswith("/find"):
            return
        text = self.textbox.toPlainText()
        if text.strip() == "":
            return

        self.messageSent(text, True)
        self.textbox.clear()

    def reset(self):
        self.chat_display.clear()
        self.above_mb_widget.setCurrentIndex(0)
        self.setChatMessageID(None)

        for msg in self.starter_messages:
            self.addMessage({"role": "assistant", "msg": msg})

    def openRasterFile(self, path: str):
        rlayer = QgsRasterLayer(path, os.path.basename(path))
        QgsProject.instance().addMapLayer(rlayer)

    def openVectorFile(self, path: str):
        vlayer = QgsVectorLayer(path, os.path.basename(path), "ogr")
        QgsProject.instance().addMapLayer(vlayer)

    def onTextUpdate(self, text):
        if text.startswith("/find"):
            self.above_mb_widget.setCurrentIndex(1)

            query = text[5:].strip()
            self.find_results.clear()

            # Search with checkbox state
            results = self.kue_find.search(
                query, filter_for_map_canvas=self.map_canvas_filter.isChecked()
            )
            for path, atime, file_type, geom_type, location in results:
                item = QListWidgetItem()
                item.setData(
                    Qt.UserRole,
                    {
                        "path": path.replace(os.path.expanduser("~"), "~"),
                        "atime": atime,
                        "location": location,
                    },
                )
                if file_type == "vector":
                    if geom_type == "Point":
                        item.setIcon(QgsIconUtils.iconPoint())
                    elif geom_type == "Line String":
                        item.setIcon(QgsIconUtils.iconLine())
                    else:
                        item.setIcon(QgsIconUtils.iconPolygon())
                elif file_type == "raster":
                    item.setIcon(QgsIconUtils.iconRaster())
                else:
                    item.setIcon(QgsIconUtils.iconDefaultLayer())
                self.find_results.addItem(item)
        else:
            self.above_mb_widget.setCurrentIndex(0)

    def maybeUpdateFindResults(self, only_for_bbox: bool = True):
        if only_for_bbox and not self.map_canvas_filter.isChecked():
            return
        # Only update if find widget is visible and has a filter
        if (
            self.isVisible()
            and self.above_mb_widget.currentIndex() == 1
            # and self.map_canvas_filter.isChecked()
            and self.textbox.toPlainText().startswith("/find")
        ):
            self.onTextUpdate(self.textbox.toPlainText())


from PyQt5.QtWidgets import QAbstractItemDelegate
from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QStyle
from PyQt5.QtCore import QMimeData, QUrl


class FileListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def mimeTypes(self):
        return ["text/uri-list"]

    def mimeData(self, items):
        data = QMimeData()
        urls = []
        path = items[0].data(Qt.UserRole)["path"].replace("~", os.path.expanduser("~"))
        urls.append(QUrl.fromLocalFile(path))
        data.setUrls(urls)
        return data


class KueFileResult(QAbstractItemDelegate):
    def __init__(self, open_vector=None, open_raster=None):
        super().__init__()
        self.open_vector = open_vector
        self.open_raster = open_raster

    def editorEvent(self, event, model, option, index):
        if event.type() == event.MouseButtonDblClick:
            path = index.data(Qt.UserRole)["path"]
            path = path.replace("~", os.path.expanduser("~"))

            # Trigger appropriate open
            if path.endswith(VECTOR_EXTENSIONS) and self.open_vector:
                self.open_vector(path)
            elif path.endswith(RASTER_EXTENSIONS) and self.open_raster:
                self.open_raster(path)
            return True
        return False

    def paint(self, painter, option, index):
        # Draw background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Draw bottom line
        painter.setPen(option.palette.dark().color())
        painter.drawLine(
            option.rect.left(),
            option.rect.bottom(),
            option.rect.right(),
            option.rect.bottom(),
        )

        # Text color depends on select state
        if option.state & QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Get the icon, draw on top of bg
        icon = index.data(Qt.DecorationRole)
        if icon:
            icon_rect = option.rect.adjusted(4, 4, -option.rect.width() + 24, -4)
            icon.paint(painter, icon_rect)

        path = index.data(Qt.UserRole)["path"]
        filename = os.path.basename(path)
        dirname = os.path.dirname(path)

        atime = index.data(Qt.UserRole)["atime"]
        location = index.data(Qt.UserRole)["location"]

        # Draw filename on first line with offset for icon
        font = painter.font()
        font.setBold(False)
        painter.setFont(font)
        text_rect = option.rect.adjusted(28, 4, -4, -int(option.rect.height() / 2))
        painter.drawText(
            text_rect, Qt.AlignLeft | Qt.AlignVCenter, f"{dirname} (opened {atime})"
        )

        # Draw dirname on second line
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            option.rect.adjusted(28, int(option.rect.height() / 2), -4, -4),
            Qt.AlignLeft | Qt.AlignVCenter,
            filename,
        )
        # Location is lighter gray
        if option.state & QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color().lighter())
        else:
            painter.setPen(option.palette.text().color().lighter())

        painter.drawText(
            option.rect.adjusted(28, int(option.rect.height() / 2), -4, -4),
            Qt.AlignRight | Qt.AlignVCenter,
            location,
        )

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 40)


class TextEditWithButtons(QTextEdit):
    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)
        self.setReadOnly(True)
        self.anchor = None

    def mousePressEvent(self, e):
        self.anchor = self.anchorAt(e.pos())
        if self.anchor:
            QApplication.setOverrideCursor(Qt.PointingHandCursor)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self.anchor:
            QDesktopServices.openUrl(QUrl(self.anchor))
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            self.anchor = None
        super().mouseReleaseEvent(e)
