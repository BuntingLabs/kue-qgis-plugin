# Copyright 2024 Bunting Labs, Inc.

from qgis.core import QgsTask, QgsApplication
from qgis.PyQt.QtCore import pyqtSignal
from qgis import processing
from processing.core.ProcessingConfig import ProcessingConfig

class KueGeoprocessingTask(QgsTask):

    responseReceived = pyqtSignal(dict)
    errorReceived = pyqtSignal(str)

    def __init__(self, plugin, actions: list):
        super().__init__(
            'Running geoprocessing tasks from Kue',
            QgsTask.CanCancel
        )
        self.plugin = plugin
        self.actions = actions

    def run(self):
        try:
            for action in self.actions:
                if not action.get('geoprocessing'):
                    continue

                alg = QgsApplication.processingRegistry().algorithmById(action['geoprocessing']['id'])
                if not alg:
                    self.errorReceived.emit(f"Geoprocessing algorithm not found: {action['geoprocessing']['id']}")
                    continue
                self.plugin.text_dock_widget.addMessage({"role": "geoprocessing", "msg": f"Running {alg.displayName()}..."})

                # Handle invalid geometries
                previous_invalid_setting = ProcessingConfig.getSetting(ProcessingConfig.FILTER_INVALID_GEOMETRIES)
                try:
                    skip_idx = ProcessingConfig.settings['FILTER_INVALID_GEOMETRIES'].options.index('Skip (ignore) features with invalid geometries')
                    ProcessingConfig.setSettingValue(ProcessingConfig.FILTER_INVALID_GEOMETRIES, skip_idx)
                except ValueError:
                    pass

                processing.runAndLoadResults(
                    alg,
                    action['geoprocessing']['parameters']
                )
                ProcessingConfig.setSettingValue(ProcessingConfig.FILTER_INVALID_GEOMETRIES, previous_invalid_setting)

            return True

        except Exception as e:
            self.errorReceived.emit(f'Geoprocessing error: {str(e)}')
            return False

    def finished(self, result):
        pass

    def cancel(self):
        super().cancel()
