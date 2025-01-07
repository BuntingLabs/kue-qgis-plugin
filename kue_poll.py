# Copyright 2024 Bunting Labs, Inc.

import json
import base64

from qgis.core import QgsTask, QgsNetworkAccessManager
from qgis.PyQt.QtCore import QSettings, pyqtSignal, QUrl, QEventLoop, QTimer
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QByteArray
from qgis.core import QgsMessageLog, Qgis
import sip


class KuePollingTask(QgsTask):
    streamingActionReceived = pyqtSignal(dict)

    def __init__(self, polling_data: dict):
        super().__init__(polling_data["description"], QgsTask.CanCancel)

        self.polling_data = polling_data
        self.setProgress(0)

    def run(self):
        try:
            url = QUrl(self.polling_data["poll_url"])
            request = QNetworkRequest(url)
            request.setHeader(QNetworkRequest.ContentTypeHeader, "text/plain")

            # Send payload in request body instead of query parameter
            payload_data = QByteArray(self.polling_data["payload"].encode())

            nam = QgsNetworkAccessManager.instance()
            reply = nam.post(request, payload_data)

            reply.readyRead.connect(lambda: self.handle_ready_read(reply))

            loop = QEventLoop()
            reply.finished.connect(loop.quit)

            timer = QTimer()
            timer.timeout.connect(
                lambda: (not sip.isdeleted(self)) and self.isCanceled() and loop.quit()
            )
            timer.start(100)

            loop.exec_()

            if self.isCanceled():
                return False

            return reply.error() == QNetworkReply.NoError

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Kue polling error: {str(e)}", "Kue", Qgis.Warning
            )
            return False

    def handle_ready_read(self, reply):
        while reply.bytesAvailable():
            line = reply.readLine().data().decode("utf-8").strip()

            # Handle progress updates
            if line.startswith("P"):
                try:
                    self.setProgress(int(line[1:]))
                    continue
                except ValueError:
                    pass

            # Handle JSON actions
            try:
                json_data = json.loads(line)
                for i, action in enumerate(json_data["actions"]):
                    for k, v in action.items():
                        json_data["actions"][i][k]["kue_action_id"] = self.polling_data[
                            "kue_action_id"
                        ]
                self.streamingActionReceived.emit(json_data)
            except json.JSONDecodeError:
                pass

    def cancel(self):
        super().cancel()
