# Copyright 2024 Bunting Labs, Inc.

import json

from qgis.core import QgsTask, QgsNetworkAccessManager
from qgis.PyQt.QtCore import QSettings, pyqtSignal, QUrl, QEventLoop, QTimer
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QByteArray
from qgis.core import QgsMessageLog, Qgis
from PyQt5.QtGui import QDesktopServices
import sip


class KueTask(QgsTask):
    responseReceived = pyqtSignal(dict)
    errorReceived = pyqtSignal(str)
    streamingContentReceived = pyqtSignal(str)
    streamingActionReceived = pyqtSignal(dict)
    chatMessageIdReceived = pyqtSignal(str)

    def __init__(
        self, user_request, kue_context, kue_version, chat_message_id: str, locale: str
    ):
        super().__init__("Waiting for Kue to respond", QgsTask.CanCancel)
        self.user_request = user_request
        self.kue_context = kue_context
        self.kue_version = kue_version
        self.chat_message_id = chat_message_id
        self.has_sent_chat_message_id = False
        self.locale = locale
        self._read_buffer = ""

    def run(self):
        try:
            url = QUrl("https://qgis-api.buntinglabs.com/kue/v1")

            request = QNetworkRequest(url)
            request.setHeader(
                QNetworkRequest.ContentTypeHeader,
                "multipart/form-data; boundary=boundary",
            )
            request.setRawHeader(
                b"x-kue-token",
                QSettings()
                .value("buntinglabs-kue/auth_token", "NO_AUTH_TOKEN")
                .encode("utf-8"),
            )
            request.setRawHeader(b"x-kue-version", self.kue_version.encode("utf-8"))
            if isinstance(self.chat_message_id, str):
                request.setRawHeader(
                    b"x-chat-session-id", self.chat_message_id.encode("utf-8")
                )
            if isinstance(self.locale, str) and len(self.locale) == 2:
                request.setRawHeader(b"Accept-Language", self.locale.encode("utf-8"))

            post_data = QByteArray()
            post_data.append(b"--boundary\r\n")
            post_data.append(b'Content-Disposition: form-data; name="req"\r\n\r\n')
            post_data.append(self.user_request.encode("utf-8"))
            post_data.append(b"\r\n--boundary\r\n")
            post_data.append(b'Content-Disposition: form-data; name="context"\r\n\r\n')
            post_data.append(json.dumps(self.kue_context).encode("utf-8"))
            post_data.append(b"\r\n--boundary\r\n")
            post_data.append(
                b'Content-Disposition: form-data; name="chat_history"\r\n\r\n'
            )
            post_data.append(json.dumps([]).encode("utf-8"))
            post_data.append(b"\r\n--boundary--\r\n")

            nam = QgsNetworkAccessManager.instance()
            reply = nam.post(request, post_data)

            reply.readyRead.connect(lambda: self.handle_ready_read(reply))

            loop = QEventLoop()
            reply.finished.connect(loop.quit)

            # Create a QTimer to periodically check if the task is cancelled
            timer = QTimer()
            timer.timeout.connect(
                lambda: (not sip.isdeleted(self)) and self.isCanceled() and loop.quit()
            )
            timer.start(100)  # Check every 100 milliseconds

            loop.exec_()

            # If cancelled prematurely
            if self.isCanceled():
                self.errorReceived.emit("Request cancelled.")
                return False

            if reply.error() == QNetworkReply.NoError:
                return True
            elif reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 402:
                self.errorReceived.emit(
                    "Kue requires a subscription. Go to buntinglabs.com/dashboard to enter your payment information."
                )
                return False
            # Handle auth failed specifically
            elif reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 403:
                kue_token = QSettings().value("buntinglabs-kue/auth_token", "")
                if kue_token:
                    self.errorReceived.emit(
                        "Sign in to buntinglabs.com to connect your account. Opening a new tab."
                    )
                    QDesktopServices.openUrl(
                        QUrl(
                            f"https://buntinglabs.com/account/register?kue_token={kue_token}"
                        )
                    )
                else:
                    self.errorReceived.emit("Restart Kue (or QGIS) to start using Kue.")

                return False
            # Unexpected server error
            elif reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 500:
                self.errorReceived.emit(
                    "Sorry: unexpected bug on Kue's server, our team will investigate."
                )
                return False
            # Bad Gateway
            elif reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 502:
                self.errorReceived.emit(
                    "Kue server seems to be down, sorry, please try again later."
                )
                return False
            else:
                QgsMessageLog.logMessage(
                    f"Kue error code: {reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)}",
                    "Kue",
                    Qgis.Warning,
                )
                self.errorReceived.emit(f"Kue error: {reply.errorString()}")
                return False

        except Exception as e:
            self.errorReceived.emit(f"Kue error: {str(e)}")
            return False

    def finished(self, result):
        pass

    def cancel(self):
        super().cancel()

    def handle_ready_read(self, reply):
        if not self.has_sent_chat_message_id:
            chat_message_id = reply.rawHeader(b"x-chat-session-id")
            if chat_message_id:
                self.chatMessageIdReceived.emit(bytes(chat_message_id).decode("utf-8"))
                self.has_sent_chat_message_id = True

        self._read_buffer += reply.readAll().data().decode("utf-8", errors="replace")

        while True:
            idx = self._read_buffer.find('{"actions":')
            if idx == -1:
                if self._read_buffer:
                    self.streamingContentReceived.emit(self._read_buffer)
                    self._read_buffer = ""
                break
            if idx > 0:
                text_chunk = self._read_buffer[:idx]
                self.streamingContentReceived.emit(text_chunk)
                self._read_buffer = self._read_buffer[idx:]

            try:
                parsed_obj, next_index = json.JSONDecoder().raw_decode(
                    self._read_buffer
                )
            except json.JSONDecodeError:
                break
            else:
                self._read_buffer = self._read_buffer[next_index:]

                self.streamingActionReceived.emit(parsed_obj)
