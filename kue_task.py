# Copyright 2024 Bunting Labs, Inc.

import json

from qgis.core import QgsTask, QgsNetworkAccessManager
from qgis.PyQt.QtCore import QSettings, pyqtSignal, QUrl, QEventLoop
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QByteArray

class KueTask(QgsTask):

    responseReceived = pyqtSignal(dict)
    errorReceived = pyqtSignal(str)

    def __init__(self, user_request, kue_context, history_str):
        super().__init__(
            'Waiting for Kue to respond',
            QgsTask.CanCancel
        )
        self.user_request = user_request
        self.kue_context = kue_context
        self.history_str = history_str
    def run(self):
        try:
            url = QUrl("https://qgis-api.buntinglabs.com/kue/v1")

            request = QNetworkRequest(url)
            request.setHeader(QNetworkRequest.ContentTypeHeader, "multipart/form-data; boundary=boundary")
            request.setRawHeader(b"x-kue-token", QSettings().value("buntinglabs-kue/auth_token", "").encode('utf-8'))

            post_data = QByteArray()
            post_data.append(b"--boundary\r\n")
            post_data.append(b"Content-Disposition: form-data; name=\"req\"\r\n\r\n")
            post_data.append(self.user_request.encode('utf-8'))
            post_data.append(b"\r\n--boundary\r\n")
            post_data.append(b"Content-Disposition: form-data; name=\"context\"\r\n\r\n")
            post_data.append(json.dumps(self.kue_context).encode('utf-8'))
            post_data.append(b"\r\n--boundary\r\n")
            post_data.append(b"Content-Disposition: form-data; name=\"chat_history\"\r\n\r\n")
            post_data.append(self.history_str.encode('utf-8'))
            post_data.append(b"\r\n--boundary--\r\n")

            nam = QgsNetworkAccessManager.instance()
            reply = nam.post(request, post_data)

            loop = QEventLoop()
            reply.finished.connect(loop.quit)
            loop.exec_()

            if reply.error() == QNetworkReply.NoError:
                content = reply.readAll().data().decode('utf-8')
                data = json.loads(content)
                self.responseReceived.emit(data)
                return True
            # Handle auth failed specifically
            elif reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 403:
                QSettings().remove("buntinglabs-kue/auth_token")
                self.errorReceived.emit('You need to link your account to use Kue. Please re-open this tab.')
                return False
            else:
                self.errorReceived.emit(f'Kue error: {reply.errorString()}')
                return False

        except Exception as e:
            self.errorReceived.emit(f'Kue error: {str(e)}')
            return False

    def finished(self, result):
        pass

    def cancel(self):
        super().cancel()
