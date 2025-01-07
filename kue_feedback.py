# Copyright Bunting Labs, Inc. 2024

from qgis.core import QgsProcessingFeedback


class KueFeedback(QgsProcessingFeedback):
    def __init__(self, *args, **kwargs):
        self.messages = []
        super().__init__(*args, **kwargs)

    def __str__(self):
        return "\n".join([str(s) for s in self.messages])

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if callable(attr) and name not in ["setProgress", "isCanceled"]:

            def wrapper(*args, **kwargs):
                if args:
                    self.messages.append(args[0])
                return attr(*args, **kwargs)

            return wrapper
        return attr
