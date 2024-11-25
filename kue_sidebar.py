# Copyright Bunting Labs, Inc. 2024

from PyQt5.QtWidgets import (
    QDockWidget,
    QStackedWidget,
    QWidget,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QFrame,
    QListWidgetItem,
    QLabel,
    QTextEdit,
)
from PyQt5.QtCore import Qt, QSettings, QTimer
from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject
from qgis.core import QgsIconUtils

from typing import Callable
import os
from .kue_find import KueFind, VECTOR_EXTENSIONS, RASTER_EXTENSIONS


class KueSidebar(QDockWidget):
    def __init__(
        self,
        iface,
        messageSent: Callable,
        authenticateUser: Callable,
        kue_find: KueFind,
    ):
        super().__init__("Kue", iface.mainWindow())

        # Properties
        self.iface = iface
        self.messageSent = messageSent
        self.authenticateUser = authenticateUser
        self.kue_find = kue_find
        # The parent widget is either kue or auth
        self.parent_widget = QStackedWidget()

        # Add auth widget
        self.auth_widget = QWidget()
        auth_layout = QVBoxLayout()
        auth_layout.setAlignment(Qt.AlignVCenter)

        title = QLabel("<h2>Kue</h2>")
        title.setContentsMargins(0, 0, 0, 10)

        description = QLabel(
            "Kue is an embedded AI assistant inside QGIS. It can read and edit your project, using cloud AI services to do so (LLMs)."
        )
        description.setWordWrap(True)
        description.setContentsMargins(0, 0, 0, 10)
        description.setMinimumWidth(300)

        pricing = QLabel(
            "Using Kue requires a subscription of $19/month (first month free). This allows us to build useful AI tools."
        )
        pricing.setWordWrap(True)
        pricing.setContentsMargins(0, 0, 0, 10)
        pricing.setMinimumWidth(300)

        login_button = QPushButton("Log In")
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

        self.textbox = QLineEdit()
        self.textbox.returnPressed.connect(self.onEnterClicked)
        self.textbox.textChanged.connect(self.onTextUpdate)

        def handleKeyPress(e):
            if e.key() == Qt.Key_Up:
                user_messages = [msg for msg in [] if msg["role"] == "user"]
                if user_messages:
                    self.textbox.setText(user_messages[-1]["msg"])
            else:
                QLineEdit.keyPressEvent(self.textbox, e)

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

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFrameShape(QFrame.NoFrame)
        self.chat_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.kue_layout = QVBoxLayout()
        self.kue_layout.setContentsMargins(0, 0, 0, 0)
        self.kue_layout.addWidget(self.chat_display)
        self.kue_widget.setLayout(self.kue_layout)

        self.find_widget = QWidget()
        self.find_layout = QVBoxLayout()
        self.find_layout.setContentsMargins(0, 0, 0, 0)

        self.find_results = QListWidget()
        self.find_results.setWordWrap(True)
        self.find_results.setFrameShape(QFrame.NoFrame)
        self.find_results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.find_results.setTextElideMode(Qt.ElideNone)
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
        self.kue_layout = QVBoxLayout()
        self.kue_layout.addWidget(self.above_mb_widget)
        self.kue_layout.addWidget(self.message_bar_widget)

        # Add message bar widget to parent widget
        self.kue_widget = QWidget()
        self.kue_widget.setLayout(self.kue_layout)
        self.parent_widget.addWidget(self.kue_widget)
        self.parent_widget.addWidget(self.auth_widget)

        self.parent_widget.setCurrentIndex(
            0 if QSettings().value("buntinglabs-kue/auth_token") else 1
        )

        self.setWidget(self.parent_widget)

        # Set up a timer to poll the QSettings value
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.checkAuthToken)
        self.poll_timer.start(5000)  # 5 seconds

    def checkAuthToken(self):
        # Check if the auth token is set and update the widget index accordingly
        if QSettings().value("buntinglabs-kue/auth_token"):
            self.parent_widget.setCurrentIndex(0)
        else:
            self.parent_widget.setCurrentIndex(1)

    def addMessage(self, msg):
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
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_display.setTextCursor(cursor)

        self.chat_display.append("")
        self.chat_display.setAlignment(
            Qt.AlignRight if msg["role"] == "user" else Qt.AlignLeft
        )
        self.chat_display.insertHtml(html)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def onChatButtonClicked(self, msg):
        # Handle button click
        from console import console
        from PyQt5.QtWidgets import QApplication

        self.iface.actionShowPythonDialog().trigger()
        console._console.console.toggleEditor(True)

        QApplication.clipboard().setText(msg["msg"])
        console._console.console.pasteEditor()

    def onEnterClicked(self):
        if self.textbox.text().startswith("/find"):
            return
        text = self.textbox.text()
        # Extract just the message text from the HTML divs/spans
        history = []
        for line in self.chat_display.toPlainText().split("\n"):
            line = line.strip()
            if line and not line.startswith("<") and not line.endswith(">"):
                history.append(line)
        self.messageSent(text, history)
        self.textbox.clear()

    def openRasterFile(self, path: str):
        rlayer = QgsRasterLayer(path, os.path.basename(path))
        QgsProject.instance().addMapLayer(rlayer)

    def openVectorFile(self, path: str):
        vlayer = QgsVectorLayer(path, os.path.basename(path), "ogr")
        QgsProject.instance().addMapLayer(vlayer)

    def onTextUpdate(self, text):
        if text.startswith("/find "):
            self.above_mb_widget.setCurrentIndex(1)

            query = text[6:]
            self.find_results.clear()

            # Search
            results = self.kue_find.search(query)
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


from PyQt5.QtWidgets import QAbstractItemDelegate
from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QStyle


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
