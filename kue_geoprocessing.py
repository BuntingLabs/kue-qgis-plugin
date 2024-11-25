# Copyright 2024 Bunting Labs, Inc.

from qgis.core import QgsTask, QgsApplication, QgsProject
from qgis.PyQt.QtCore import pyqtSignal
from qgis import processing
from processing.core.ProcessingConfig import ProcessingConfig


class KueGeoprocessingTask(QgsTask):
    responseReceived = pyqtSignal(dict)
    errorReceived = pyqtSignal(str)

    def __init__(self, plugin, actions: list):
        super().__init__("Running geoprocessing tasks from Kue", QgsTask.CanCancel)
        self.plugin = plugin
        self.actions = actions

    def run(self):
        try:
            # Special values
            SEC_LAST_LAYER_ID = None

            for action in self.actions:
                if not action.get("geoprocessing"):
                    continue

                alg = QgsApplication.processingRegistry().algorithmById(
                    action["geoprocessing"]["id"]
                )
                if not alg:
                    self.errorReceived.emit(
                        f"Geoprocessing algorithm not found: {action['geoprocessing']['id']}"
                    )
                    continue
                self.plugin.text_dock_widget.addMessage(
                    {"role": "geoprocessing", "msg": f"Running {alg.displayName()}..."}
                )

                # Handle invalid geometries
                previous_invalid_setting = ProcessingConfig.getSetting(
                    ProcessingConfig.FILTER_INVALID_GEOMETRIES
                )
                try:
                    skip_idx = ProcessingConfig.settings[
                        "FILTER_INVALID_GEOMETRIES"
                    ].options.index("Skip (ignore) features with invalid geometries")
                    ProcessingConfig.setSettingValue(
                        ProcessingConfig.FILTER_INVALID_GEOMETRIES, skip_idx
                    )
                except ValueError:
                    pass

                # Replace any parameters with special values
                for key, value in action["geoprocessing"]["parameters"].items():
                    if value == "§LAST_LAYER" and SEC_LAST_LAYER_ID:
                        last_layer_source = QgsProject.instance().mapLayer(
                            SEC_LAST_LAYER_ID
                        )
                        if last_layer_source:
                            action["geoprocessing"]["parameters"][key] = (
                                last_layer_source.source()
                            )
                    elif value.startswith("§"):
                        # Allow referring to layers by ID, instead of source
                        layer_id = value[1:]
                        layer = QgsProject.instance().mapLayer(layer_id)
                        if layer:
                            action["geoprocessing"]["parameters"][key] = layer.source()

                output = processing.runAndLoadResults(
                    alg, action["geoprocessing"]["parameters"]
                )
                if "OUTPUT" in output:
                    # It gives us the layer ID
                    SEC_LAST_LAYER_ID = output["OUTPUT"]

                ProcessingConfig.setSettingValue(
                    ProcessingConfig.FILTER_INVALID_GEOMETRIES, previous_invalid_setting
                )

            return True

        except Exception as e:
            self.errorReceived.emit(f"Geoprocessing error: {str(e)}")
            return False

    def finished(self, result):
        pass

    def cancel(self):
        super().cancel()
