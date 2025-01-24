# Copyright 2024 Bunting Labs, Inc.

import os
import random
import secrets
import string
from itertools import islice
import tempfile
import json
from enum import Enum
import base64
from typing import Callable
from PyQt5.QtWidgets import QAction, QDialog
from PyQt5.QtGui import QIcon, QColor, QDesktopServices
from PyQt5.QtCore import QSettings, Qt, QUrl, QVariant, QDate

from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsProject,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsRectangle,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsRasterLayer,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsDataSourceUri,
    QgsExpression,
    QgsFeatureRequest,
    QgsVirtualLayerDefinition,
    NULL as QgsNull,
    QgsField,
    QgsVectorFileWriter,
    QgsVectorFileWriterTask,
)
from qgis.core import QgsFillSymbol

from .kue_task import KueTask
from .kue_messages import (
    KUE_INTRODUCTION_MESSAGES,
    KUE_ASK_KUE,
    KueResponseStatus,
    status_to_color,
)
from .kue_sidebar import KueSidebar
from .kue_find import KueFind
from .kue_feedback import KueFeedback
from .kue_poll import KuePollingTask


class KuePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.settings = QSettings()

        self.kue_find = KueFind(iface)

        # Read the plugin version
        try:
            plugin_metadata = os.path.join(os.path.dirname(__file__), "metadata.txt")
            with open(plugin_metadata, "r") as f:
                for line in f.readlines():
                    if line.startswith("version="):
                        self.plugin_version = line.split("=")[1].strip()
        except:
            self.plugin_version = "N/A"

        self.kue_icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.kue_action = QAction(
            QIcon(self.kue_icon_path),
            "<b>Open Kue</b><p>Use an AI assistant that can read and edit your project</p>",
            None,
        )

        self.chat_message_id = None

        self.text_dock_widget = None

        # Load the greeting message
        locale = QSettings().value("locale/userLocale", QgsApplication.locale())
        self.lang = locale[:2] if isinstance(locale, str) and len(locale) >= 2 else "en"

        self.starter_messages = KUE_INTRODUCTION_MESSAGES.get(
            self.lang, KUE_INTRODUCTION_MESSAGES["en"]
        )
        self.ask_kue_message = KUE_ASK_KUE.get(self.lang, KUE_ASK_KUE["en"])

        self.task_trash = []

    # ================================================
    # GUI management
    # ================================================

    def initGui(self):
        self.iface.mainWindow().addAction(self.kue_action)
        self.kue_action.triggered.connect(self.toggleKue)
        self.iface.addToolBarIcon(self.kue_action)

        self.text_dock_widget = KueSidebar(
            self.iface,
            self.messageSent,
            self.authenticateUser,
            self.kue_find,
            self.ask_kue_message,
            self.lang,
            self.setChatMessageID,
            self.starter_messages,
        )
        self.text_dock_widget.hide()

    def unload(self):
        self.iface.removeToolBarIcon(self.kue_action)

        if self.text_dock_widget:
            # Remove from main window
            self.iface.removeDockWidget(self.text_dock_widget)
            # Schedule widget for deletion
            self.text_dock_widget.deleteLater()
            self.text_dock_widget = None

    def toggleKue(self):
        if self.text_dock_widget.isVisible():
            self.text_dock_widget.hide()
        else:
            self.text_dock_widget.show()
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.text_dock_widget)

    def handleLinkClick(self, url):
        # Handle link clicks - url is a string containing the clicked URL
        QDesktopServices.openUrl(QUrl(url))

    # ================================================
    # Authentication
    # ================================================

    def authenticateUser(self):
        alphabet = string.ascii_letters + string.digits
        key = "".join(secrets.choice(alphabet) for _ in range(64))

        QDesktopServices.openUrl(
            QUrl(f"https://buntinglabs.com/account/register?kue_token={key}")
        )
        QSettings().setValue("buntinglabs-kue/auth_token", key)

    # ================================================
    # AI Management (inputs and outputs)
    # ================================================

    def formatAttributePreview(self, attr):
        if isinstance(attr, QDate):
            return attr.toString("yyyy-MM-dd")  # ISO 8601
        elif isinstance(attr, float):
            return float(f"{attr:.6g}")  # 6 significant digits
        elif isinstance(attr, int):
            return attr
        elif attr == QgsNull:
            return None
        return str(attr)[:28] + "..." if len(str(attr)) > 28 else str(attr)

    def createKueContext(self):
        project_crs = QgsProject.instance().crs()
        layers = QgsProject.instance().mapLayers().values()
        vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
        raster_layers = [layer for layer in layers if isinstance(layer, QgsRasterLayer)]
        # Transform centroid and bbox to EPSG:4326 if needed
        centroid = self.iface.mapCanvas().extent().center()
        qgis_bbox = self.iface.mapCanvas().extent()

        if project_crs != QgsCoordinateReferenceSystem("EPSG:4326"):
            try:
                transform = QgsCoordinateTransform(
                    project_crs,
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    QgsProject.instance(),
                )
                qgis_bbox = transform.transformBoundingBox(qgis_bbox)
                centroid = transform.transform(centroid)
            except Exception as e:
                print(f"Failed to transform to EPSG:4326: {e}")
                pass

        return {
            "projection": project_crs.authid(),
            "locale": QSettings().value("locale/userLocale"),
            "bbox": [
                float(format(qgis_bbox.xMinimum(), ".6f")),
                float(format(qgis_bbox.yMinimum(), ".6f")),
                float(format(qgis_bbox.xMaximum(), ".6f")),
                float(format(qgis_bbox.yMaximum(), ".6f")),
            ],
            "centroid": {
                "lat": float(format(centroid.y(), ".6f")),
                "lon": float(format(centroid.x(), ".6f")),
            },
            "vector_layers": [
                {
                    "id": layer.id(),
                    "layer_name": layer.name(),
                    "visible": is_layer_visible(layer),
                    "layer_type": QgsWkbTypes.displayString(layer.wkbType()),
                    "provider": layer.dataProvider().name(),
                    "symbology": self.getLayerSymbology(layer),
                    "num_features": layer.featureCount(),
                    "crs": layer.crs().authid(),
                    # For now, give only 1 feature (if present) with islice
                    "attribute_example": [
                        {
                            str(field.name()): self.formatAttributePreview(
                                feature[field.name()]
                            )
                            for field in layer.fields()
                            if field.name() in feature.fields().names()
                        }
                        for feature in islice(layer.getFeatures(), 1)
                    ],
                    "subset_string": layer.subsetString() or None,
                }
                for layer in vector_layers
            ],
            "raster_layers": [
                {
                    "id": layer.id(),
                    "layer_name": layer.name(),
                    "visible": is_layer_visible(layer),
                    "crs": layer.crs().authid(),
                    "provider_type": layer.providerType(),
                    "source": layer.source() if layer.providerType() == "wms" else None,
                    "bands": layer.bandCount(),
                }
                for layer in raster_layers
            ],
        }

    def getLayerSymbology(self, layer):
        renderer = layer.renderer()
        if isinstance(renderer, QgsFillSymbol):
            symbol = renderer.symbol()
            return {
                "type": "fill",
                "color": symbol.color().name(),
                "opacity": symbol.opacity(),
            }
        else:
            return {"type": "unknown"}

    def setProjection(self, projection_action):
        crs = QgsCoordinateReferenceSystem(f"EPSG:{projection_action['epsg_code']}")
        if crs.isValid():
            QgsProject.instance().setCrs(crs)
            return {
                "status": KueResponseStatus.OK,
                "message": "Set projection to EPSG:"
                + str(projection_action["epsg_code"]),
            }
        else:
            return {"status": KueResponseStatus.ERROR, "message": "Invalid CRS"}

    def handleKueResponse(self, data):
        def handle_response(r):
            for action in data.get("actions", []):
                for k, v in action.items():
                    if "kue_action_id" in v:
                        r["kue_action_id"] = v["kue_action_id"]
                    if "kue_action_svg" in v:
                        r["kue_action_svg"] = v["kue_action_svg"]
            if "kue_action_id" in r:
                if not ("status" in r and r["status"] == KueResponseStatus.POLLING):
                    self.messageSent(json.dumps(r), False)

                if "kue_action_svg" in r:
                    self.text_dock_widget.addAction(r)

        resp = self.actionsToResponses(data, handle_response)
        if resp:
            handle_response(resp)

    def actionsToResponses(self, data, callback: Callable):
        for action in data.get("actions", []):
            if action.get("geoprocessing"):
                from qgis.core import (
                    QgsProcessingContext,
                    QgsProcessingAlgRunnerTask,
                    QgsProcessingFeedback,
                )
                from processing.core.ProcessingConfig import ProcessingConfig

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

                alg = QgsApplication.processingRegistry().algorithmById(
                    action["geoprocessing"]["id"]
                )
                feedback = KueFeedback()
                self.task_trash.append(feedback)
                context = QgsProcessingContext()
                self.task_trash.append(context)
                context.setProject(QgsProject.instance())

                def transform_parameter(value: str) -> str:
                    if value.startswith("§"):
                        layer_id = value[1:]
                        layer = QgsProject.instance().mapLayer(layer_id)
                        if layer:
                            return layer.source()
                        if len(QgsProject.instance().mapLayersByName(layer_id)) == 1:
                            return (
                                QgsProject.instance()
                                .mapLayersByName(layer_id)[0]
                                .source()
                            )
                    return value

                # Transform parameters if needed
                parameters = action["geoprocessing"]["parameters"]
                for key, value in parameters.items():
                    if isinstance(value, str):
                        parameters[key] = transform_parameter(value)
                    elif isinstance(value, list):
                        parameters[key] = [
                            transform_parameter(v) if isinstance(v, str) else v
                            for v in value
                        ]
                self.task_trash.append(parameters)
                self.task_trash.append(alg)

                task = QgsProcessingAlgRunnerTask(alg, parameters, context, feedback)
                self.task_trash.append(task)

                def completed(successful: bool, results: dict):
                    ProcessingConfig.setSettingValue(
                        ProcessingConfig.FILTER_INVALID_GEOMETRIES,
                        previous_invalid_setting,
                    )

                    if successful and "OUTPUT" in results:
                        layer = None

                        output_layer = context.getMapLayer(results["OUTPUT"])
                        if output_layer:
                            layer = context.takeResultLayer(output_layer.id())
                        elif os.path.exists(results["OUTPUT"]) and os.path.isfile(
                            results["OUTPUT"]
                        ):
                            if results["OUTPUT"].endswith(".tif"):
                                layer = QgsRasterLayer(results["OUTPUT"], "OUTPUT")
                            else:
                                layer = QgsVectorLayer(
                                    results["OUTPUT"], "OUTPUT", "ogr"
                                )

                        if layer and layer.isValid():
                            QgsProject.instance().addMapLayer(layer)
                            callback(
                                {
                                    "status": KueResponseStatus.OK,
                                    "feature_count": layer.featureCount()
                                    if isinstance(layer, QgsVectorLayer)
                                    else None,
                                    "results": results,
                                    "message": f"{alg.displayName()} completed",
                                    "feedback": str(feedback),
                                }
                            )
                        else:
                            callback(
                                {
                                    "status": KueResponseStatus.AMBIGUOUS,
                                    "results": results,
                                    "message": f"{alg.displayName()} completed but output layer is invalid or did not exist",
                                    "feedback": str(feedback),
                                }
                            )
                    elif successful:
                        callback(
                            {
                                "status": KueResponseStatus.OK,
                                "results": results,
                                "message": f"{alg.displayName()} completed",
                                "feedback": str(feedback),
                            }
                        )
                    else:
                        # Handle failure response
                        if feedback.isCanceled():
                            callback(
                                {
                                    "status": KueResponseStatus.USER_CANCELLED,
                                    "message": f"{alg.displayName()} cancelled by user",
                                    "feedback": str(feedback),
                                }
                            )
                        else:
                            callback(
                                {
                                    "status": KueResponseStatus.ERROR,
                                    "message": f"{alg.displayName()} failed: {results}",
                                    "feedback": str(feedback),
                                }
                            )

                task.executed.connect(completed)

                # Start the task
                QgsApplication.taskManager().addTask(task)
                return

            # Handle all non-geoprocessing actions immediately
            if action.get("add_xyz_layer"):
                return self.addXYZLayer(action["add_xyz_layer"])
            if action.get("add_wfs_layer"):
                return self.createNewVectorLayer(action["add_wfs_layer"])
            if action.get("create_new_vector_layer"):
                return self.createNewVectorLayer(action["create_new_vector_layer"])
            if action.get("add_wms_layer"):
                return self.addWMSLayer(action["add_wms_layer"])
            if action.get("add_cloud_vector_layer"):
                return self.addCloudVectorLayer(action["add_cloud_vector_layer"])
            if action.get("poll"):
                polling_task = KuePollingTask(action["poll"])
                polling_task.streamingActionReceived.connect(
                    lambda action: self.handleKueResponse(action)
                )
                polling_task.taskCompleted.connect(print)
                polling_task.taskTerminated.connect(print)
                self.task_trash.append(polling_task)
                QgsApplication.taskManager().addTask(polling_task)

                # Add to sidebar, orange as its loading
                return {
                    "status": KueResponseStatus.POLLING,
                    "message": action["poll"]["description"],
                }
            if action.get("add_arcgis_rest_server_layer"):
                return self.addArcGISFeatureServerLayer(
                    action["add_arcgis_rest_server_layer"]
                )
            if action.get("set_vector_single_symbol"):
                return self.setVectorSingleSymbology(action["set_vector_single_symbol"])
            if action.get("set_vector_categorized_symbol"):
                return self.setVectorCategorizedSymbol(
                    action["set_vector_categorized_symbol"]
                )
            if action.get("set_vector_graduated_symbol"):
                return self.setVectorGraduatedSymbol(
                    action["set_vector_graduated_symbol"]
                )
            if action.get("zoom_to_bounding_box"):
                return self.zoomToBoundingBox(action["zoom_to_bounding_box"])
            if action.get("set_vector_labels"):
                return self.setVectorLabels(action["set_vector_labels"])
            if action.get("set_layer_visibility"):
                return self.setLayerVisibility(action["set_layer_visibility"])
            if action.get("set_vector_layer_subset_string"):
                return self.setVectorLayerSubsetString(
                    action["set_vector_layer_subset_string"]
                )
            if action.get("select_features"):
                return self.selectFeatures(action["select_features"])
            if action.get("set_projection"):
                return self.setProjection(action["set_projection"])
            if action.get("apply_qml_style"):
                return self.applyQMLStyle(action["apply_qml_style"])
            if action.get("add_vector_field"):
                return self.addVectorField(action["add_vector_field"])
            if action.get("saveVectorLayerToFile"):
                return self.saveVectorLayerToFile(action["saveVectorLayerToFile"])

    def applyQMLStyle(self, style_json):
        vl = QgsProject.instance().mapLayer(style_json["layer_id"])
        if vl:
            with tempfile.NamedTemporaryFile(suffix=".qml") as temp_file:
                qml_style = style_json["style"]
                qml_style = qml_style.replace(
                    "§LAYER_GEOMETRY_TYPE", str(int(vl.geometryType()))
                )

                temp_file.write(qml_style.encode("utf-8"))
                temp_file.flush()
                result_flag = False
                output = vl.loadNamedStyle(temp_file.name, result_flag)
                # Cautiously interpret output. not sure if its documented
                if isinstance(output, tuple) and len(output) == 2:
                    result_error, was_ok = output
                    if not was_ok:
                        return {
                            "status": KueResponseStatus.ERROR,
                            "message": f"Could not style layer: {result_error}",
                        }
                vl.triggerRepaint()
                return {
                    "status": KueResponseStatus.OK,
                    "message": f"{vl.name()}: styled",
                }

        return {
            "status": KueResponseStatus.ERROR,
            "message": f"No layer ID {style_json['layer_id']} found",
        }

    def setVectorLabels(self, label_action):
        if "layer_id" in label_action:
            layer = QgsProject.instance().mapLayer(label_action["layer_id"])
        else:
            layers = QgsProject.instance().mapLayersByName(label_action["layer_name"])
            if not layers:
                return {
                    "status": KueResponseStatus.ERROR,
                    "message": "Kue could not find vector layer",
                }
            layer = layers[0]
        if isinstance(layer, QgsVectorLayer):
            label_settings = QgsPalLayerSettings()
            label_settings.fieldName = label_action["attribute_name"]
            label_settings.enabled = True

            text_format = QgsTextFormat()
            text_format.setSize(label_action.get("font_size", 10))
            if label_action["text_buffer_size_mm"] > 0:
                buffer_settings = QgsTextBufferSettings()
                buffer_settings.setEnabled(True)
                buffer_settings.setSize(label_action["text_buffer_size_mm"])
                buffer_settings.setColor(QColor(255, 255, 255))
                buffer_settings.setOpacity(0.8)
                text_format.setBuffer(buffer_settings)
            label_settings.setFormat(text_format)
            layer_settings = QgsVectorLayerSimpleLabeling(label_settings)
            layer.setLabelsEnabled(True)
            layer.setLabeling(layer_settings)
            layer.triggerRepaint()

            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: labels enabled",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": "Kue could not find vector layer",
            }

    def zoomToBoundingBox(self, bbox):
        source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        rectangle = QgsRectangle(bbox["xmin"], bbox["ymin"], bbox["xmax"], bbox["ymax"])
        dest_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        try:
            transform = QgsCoordinateTransform(
                source_crs, dest_crs, QgsProject.instance()
            )
            transformed_rectangle = transform.transformBoundingBox(rectangle)
            self.iface.mapCanvas().setExtent(transformed_rectangle)
            self.iface.mapCanvas().refresh()
        except Exception as e:
            self.handleKueError(f"Failed to zoom to bounding box: {e}")
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Failed to zoom to bounding box: {e}",
            }
        return {"status": KueResponseStatus.OK, "message": "Zoomed"}

    def openAttributeTable(self, layer_name):
        if (
            "layer_id" in layer_name
        ):  # Assuming layer_name could be a dict with layer_id
            layer = QgsProject.instance().mapLayer(layer_name["layer_id"])
        else:
            layers = QgsProject.instance().mapLayersByName(layer_name)
            if not layers:
                return
            layer = layers[0]
        if layer and isinstance(layer, QgsVectorLayer):
            self.iface.openAttributeTable(layer)

    def saveVectorLayerToFile(self, save_action):
        try:
            from qgis.gui import QgsVectorLayerSaveAsDialog
        except ImportError:
            return {
                "status": KueResponseStatus.ERROR,
                "message": "Saving vector layers to file is not supported in QGIS versions prior to 3.30.",
            }

        layer = QgsProject.instance().mapLayer(save_action["layer_id"])
        if not layer or not isinstance(layer, QgsVectorLayer):
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Kue could not find vector layer: {save_action['layer_id']}",
            }

        # Pass as few options as possible
        dialog = QgsVectorLayerSaveAsDialog(
            layer, options=QgsVectorLayerSaveAsDialog.Options()
        )
        dialog.setAddToCanvas(False)  # manual

        if dialog.exec() != QDialog.Accepted:
            return {
                "status": KueResponseStatus.ERROR,
                "message": "User cancelled saving vector layer",
            }
        if dialog.crs() != layer.crs():
            return {
                "status": KueResponseStatus.ERROR,
                "message": "Kue export does not support changing CRS",
            }

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = dialog.format()
        options.layerName = dialog.layerName()
        options.includeZ = dialog.includeZ()
        options.attributes = dialog.selectedAttributes()
        options.fileEncoding = dialog.encoding()
        options.symbologyExport = dialog.symbologyExport()
        options.symbologyScale = dialog.scale()
        options.onlySelectedFeatures = dialog.onlySelected()
        options.attributesExportNames = dialog.attributesExportNames()
        options.skipAttributeCreation = not dialog.selectedAttributes()
        options.forceMulti = dialog.forceMulti()
        options.datasourceOptions = dialog.datasourceOptions()
        options.layerOptions = dialog.layerOptions()
        options.saveMetadata = dialog.persistMetadata()
        options.layerMetadata = layer.metadata()

        self.text_dock_widget.addMessage(
            {
                "role": "assistant",
                "msg": f"{layer.name()}: exporting...",
                "has_button": False,
            }
        )

        # Create a separate task, could take a while
        writerTask = QgsVectorFileWriterTask(layer, dialog.fileName(), options)

        def add_saved_layer(o_filename: str, o_layer_name: str):
            uri = o_filename
            if o_layer_name:
                uri = f"{uri}|layername={o_layer_name}"
            QgsProject.instance().addMapLayer(QgsVectorLayer(uri, o_layer_name, "ogr"))

        # when writer is successful:
        writerTask.completed.connect(
            lambda: add_saved_layer(dialog.fileName(), dialog.layerName())
        )
        writerTask.completed.connect(
            lambda: self.text_dock_widget.addMessage(
                {
                    "role": "assistant",
                    "msg": f"{layer.name()}: exported",
                    "has_button": False,
                }
            )
        )
        writerTask.errorOccurred.connect(
            lambda: self.handleKueError("Failed to export layer")
        )

        QgsApplication.taskManager().addTask(writerTask)

        return {
            "status": KueResponseStatus.OK,
            "message": f"{layer.name()}: exporting...",
        }

    def addVectorField(self, field_action):
        layer = QgsProject.instance().mapLayer(field_action["layer_id"])
        if not layer or not isinstance(layer, QgsVectorLayer):
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Kue could not find vector layer: {field_action['layer_id']}",
            }

        FIELD_TYPES = {
            "string": QVariant.String,
            "int": QVariant.Int,
            "double": QVariant.Double,
            "date": QVariant.Date,
        }

        if layer.fields().indexOf(field_action["field_name"]) != -1:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Attribute {field_action['field_name']} already exists",
            }

        layer.startEditing()
        layer.addAttribute(
            QgsField(
                field_action["field_name"],
                FIELD_TYPES[field_action["field_type"]],
            )
        )

        return {
            "status": KueResponseStatus.OK,
            "message": f"{layer.name()}: field {field_action['field_name']} added",
        }
        # Don't commit changes, let the user do that

    def setVectorLayerSubsetString(self, subset_action):
        if "layer_id" in subset_action:
            layer = QgsProject.instance().mapLayer(subset_action["layer_id"])
        else:
            layers = QgsProject.instance().mapLayersByName(subset_action["layer_name"])
            if not layers:
                return
            layer = layers[0]
        if layer and isinstance(layer, QgsVectorLayer):
            if not layer.setSubsetString(subset_action["subset_string"]):
                return {
                    "status": KueResponseStatus.ERROR,
                    "message": "Failed to set subset string",
                }
            else:
                return {
                    "status": KueResponseStatus.OK,
                    "message": f"{layer.name()}: {subset_action['subset_string']}",
                }

    def selectFeatures(self, select_action):
        layer = QgsProject.instance().mapLayer(select_action["layer_id"])
        if layer and isinstance(layer, QgsVectorLayer):
            expression = QgsExpression(select_action["sql_expression"])
            if expression.hasParserError():
                return {
                    "status": KueResponseStatus.ERROR,
                    "message": f"Kue created invalid SQL query: {expression.parserErrorString()}",
                }

            request = QgsFeatureRequest(expression)
            matching_features = list(layer.getFeatures(request))
            layer.selectByIds([feature.id() for feature in matching_features])
            total_count = layer.featureCount()
            layer_name = layer.name()

            return {
                "status": KueResponseStatus.OK,
                "selected_features": len(matching_features),
                "layer_feature_count": total_count,
                "sql_expression": select_action["sql_expression"],
                "message": f"{layer_name}: `{select_action['sql_expression']}` ({len(matching_features)}/{total_count})",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Kue could not find vector layer: {select_action['layer_id']}",
            }

    def setVectorSingleSymbology(self, symbology_action):
        if "layer_id" in symbology_action:
            layer = QgsProject.instance().mapLayer(symbology_action["layer_id"])
        else:
            layers = QgsProject.instance().mapLayersByName(
                symbology_action["layer_name"]
            )
            if not layers:
                return
            layer = layers[0]
        if layer and isinstance(layer, QgsVectorLayer):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(symbology_action["color"]))
            symbol.setOpacity(symbology_action["opacity"])
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: set single symbol",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Kue could not find vector layer: {symbology_action['layer_name']}",
            }

    def setVectorCategorizedSymbol(self, symbology_action):
        if "layer_id" in symbology_action:
            layer = QgsProject.instance().mapLayer(symbology_action["layer_id"])
        else:
            layers = QgsProject.instance().mapLayersByName(
                symbology_action["layer_name"]
            )
            if not layers:
                return {
                    "status": KueResponseStatus.ERROR,
                    "message": "Kue could not find vector layer",
                }
            layer = layers[0]
        if layer and isinstance(layer, QgsVectorLayer):
            field_name = symbology_action["field_name"]
            unique_values = layer.uniqueValues(layer.fields().indexFromName(field_name))
            categories = []

            for value in unique_values:
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                if symbology_action["colormap"] == "random":
                    symbol.setColor(
                        QColor(
                            random.randint(0, 255),
                            random.randint(0, 255),
                            random.randint(0, 255),
                        )
                    )
                # TODO other color maps
                symbol.setOpacity(symbology_action["opacity"])
                category = QgsRendererCategory(value, symbol, str(value))
                categories.append(category)

            renderer = QgsCategorizedSymbolRenderer(field_name, categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: set categorized symbol",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": "Kue could not find vector layer",
            }

    def setVectorGraduatedSymbol(self, symbology_action):
        if "layer_id" in symbology_action:
            layer = QgsProject.instance().mapLayer(symbology_action["layer_id"])
        else:
            layers = QgsProject.instance().mapLayersByName(
                symbology_action["layer_name"]
            )
            if not layers:
                return {
                    "status": KueResponseStatus.ERROR,
                    "message": "Kue could not find vector layer",
                }
            layer = layers[0]
        if layer and isinstance(layer, QgsVectorLayer):
            field_name = symbology_action["field_name"]
            classes = symbology_action["classes"]

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setOpacity(symbology_action["opacity"])

            # Create graduated renderer
            renderer = QgsGraduatedSymbolRenderer(field_name)
            renderer.setSourceSymbol(symbol.clone())

            # Calculate class breaks using equal interval
            field_index = layer.fields().indexFromName(field_name)
            min_val, max_val = layer.minimumAndMaximumValue(field_index)
            if min_val is None or max_val is None:
                return {
                    "status": KueResponseStatus.ERROR,
                    "message": f"Can't read min/max values for {layer.name()}, try re-exporting to a Shapefile.",
                }
            interval = (max_val - min_val) / classes

            # Choose one of 4 diverging color ramps randomly
            color_ramps = [
                [QColor(208, 28, 139), QColor(77, 172, 38)],  # Pink-Green
                [QColor(184, 55, 115), QColor(53, 151, 143)],  # Purple-Teal
                [QColor(230, 97, 1), QColor(94, 113, 106)],  # Orange-Gray
                [QColor(214, 47, 39), QColor(33, 102, 172)],  # Red-Blue
            ]
            start_color, end_color = random.choice(color_ramps)

            # Create class breaks and assign symbols
            for i in range(classes):
                lower = min_val + (interval * i)
                upper = min_val + (interval * (i + 1))

                # Calculate interpolated color
                t = i / (classes - 1) if classes > 1 else 0
                r = int(start_color.red() + (end_color.red() - start_color.red()) * t)
                g = int(
                    start_color.green() + (end_color.green() - start_color.green()) * t
                )
                b = int(
                    start_color.blue() + (end_color.blue() - start_color.blue()) * t
                )

                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                symbol.setColor(QColor(r, g, b))
                symbol.setOpacity(symbology_action["opacity"])

                range_label = f"{lower:.2f} - {upper:.2f}"
                renderer.addClassRange(
                    QgsRendererRange(lower, upper, symbol, range_label)
                )

            layer.setRenderer(renderer)
            layer.triggerRepaint()

            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: set graduated symbol",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": "Kue could not find vector layer",
            }

    def addXYZLayer(self, xyz_action):
        uri = f"type=xyz&url={xyz_action['url']}"
        layer = QgsRasterLayer(uri, xyz_action["name"], "wms")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: added",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Failed to add XYZ layer: {xyz_action['name']}",
            }

    def createNewVectorLayer(self, new_vector_layer_action):
        layer = QgsVectorLayer(
            new_vector_layer_action["url"],
            new_vector_layer_action["name"],
            new_vector_layer_action.get("provider", "WFS"),
        )
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: added",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Failed to add vector layer: {new_vector_layer_action['name']}",
            }

    def addWMSLayer(self, wms_action):
        uri = f"url={wms_action['url']}"
        layer = QgsRasterLayer(uri, wms_action["name"], "wms")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: added",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Failed to add WMS layer: {wms_action['name']}",
            }

    def addArcGISFeatureServerLayer(self, arcgis_feature_server_action):
        uri = QgsDataSourceUri()
        uri.setParam("crs", "EPSG:3857")
        uri.setParam("url", arcgis_feature_server_action["url"])
        layer = QgsVectorLayer(
            uri.uri(), arcgis_feature_server_action["name"], "arcgisfeatureserver"
        )
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: added",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Failed to add ArcGIS feature server layer: {arcgis_feature_server_action['name']}",
            }

    def addCloudVectorLayer(self, cloud_vector_action):
        layer = QgsVectorLayer(
            f"/vsicurl/{cloud_vector_action['url']}", cloud_vector_action["name"], "ogr"
        )
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)

            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: added",
                "feature_count": layer.featureCount(),
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Failed to add cloud vector layer: {cloud_vector_action['name']}",
            }

    def setLayerVisibility(self, visibility_action):
        if "layer_id" in visibility_action:
            layer = QgsProject.instance().mapLayer(visibility_action["layer_id"])
        else:
            layers = QgsProject.instance().mapLayersByName(
                visibility_action["layer_name"]
            )
            if not layers:
                return
            layer = layers[0]
        tree_layer = QgsProject.instance().layerTreeRoot().findLayer(layer)
        if tree_layer:
            tree_layer.setItemVisibilityChecked(visibility_action["visible"])
            self.iface.mapCanvas().refresh()
            return {
                "status": KueResponseStatus.OK,
                "message": f"{layer.name()}: set visibility",
            }
        else:
            return {
                "status": KueResponseStatus.ERROR,
                "message": f"Kue could not find layer: {visibility_action['layer_name']}",
            }

    def handleKueError(self, msg):
        self.text_dock_widget.addError(msg)

    def setChatMessageID(self, chat_message_id: str):
        self.chat_message_id = chat_message_id

    def messageSent(self, text: str, addToSidebar: bool):
        kue_task = KueTask(
            text,
            self.createKueContext(),
            self.plugin_version,
            self.chat_message_id,
            self.lang,
        )

        kue_task.chatMessageIdReceived.connect(self.setChatMessageID)
        kue_task.responseReceived.connect(self.handleKueResponse)
        kue_task.errorReceived.connect(self.handleKueError)

        kue_task.streamingContentReceived.connect(
            lambda chars: self.text_dock_widget.insertChars(chars)
        )

        kue_task.streamingActionReceived.connect(
            lambda action: self.handleKueResponse(action)
        )

        QgsApplication.taskManager().addTask(kue_task)
        self.task_trash.append(kue_task)

        if addToSidebar:
            self.text_dock_widget.addMessage(
                {"role": "user", "msg": text, "has_button": False}
            )

        self.text_dock_widget.chat_display.append("")
        self.text_dock_widget.chat_display.setAlignment(Qt.AlignLeft)


def is_layer_visible(layer):
    return QgsProject.instance().layerTreeRoot().findLayer(layer).isVisible()
