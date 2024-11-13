# Copyright 2024 Bunting Labs, Inc.

import os
import random
import secrets
import string
from itertools import islice

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QLineEdit, QPushButton, QAction, 
    QHBoxLayout, QWidget, QDockWidget, QScrollArea, QFrame
)
from PyQt5.QtGui import QIcon, QColor, QDesktopServices
from PyQt5.QtCore import (
    QSettings, Qt, QUrl
)

from qgis.core import (
    QgsApplication, QgsVectorLayer, QgsWkbTypes,
    QgsProject, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsTextBufferSettings, QgsTextFormat, QgsRectangle,
    QgsSingleSymbolRenderer, QgsSymbol, QgsCategorizedSymbolRenderer,
    QgsRendererCategory, QgsRasterLayer, QgsGraduatedSymbolRenderer,
    QgsRendererRange, QgsDataSourceUri
)
from qgis import processing
from qgis.core import QgsFillSymbol

from .kue_task import KueTask
from .kue_messages import KUE_INTRODUCTION_MESSAGES
from .kue_sidebar import KueSidebar
from .kue_find import KueFind

class KuePlugin:

    def __init__(self, iface):
        self.iface = iface
        self.settings = QSettings()

        self.kue_find = KueFind()

        # Read the plugin version
        try:
            plugin_metadata = os.path.join(os.path.dirname(__file__), "metadata.txt")
            with open(plugin_metadata, 'r') as f:
                for line in f.readlines():
                    if line.startswith('version='):
                        self.plugin_version = line.split('=')[1].strip()
        except:
            self.plugin_version = 'N/A'

        self.kue_icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.kue_action = QAction(QIcon(self.kue_icon_path), '<b>Open Kue</b><p>Use an AI assistant that can read and edit your project</p>', None)

        self.text_dock_widget = None

        # Load the greeting message 
        locale = QSettings().value('locale/userLocale', 'en_US')
        lang = locale[2:] if isinstance(locale, str) and len(locale) > 2 else 'en'
        self.starter_messages = KUE_INTRODUCTION_MESSAGES.get(
            lang,
            KUE_INTRODUCTION_MESSAGES['en']
        )

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
            self.onEnterClicked,
            self.authenticateUser,
            self.kue_find
        )

        for msg in self.starter_messages:
            self.text_dock_widget.addMessage({"role": "assistant", "msg": msg})

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
        key = ''.join(secrets.choice(alphabet) for _ in range(64))

        QDesktopServices.openUrl(QUrl(f"https://buntinglabs.com/account/register?kue_token={key}"))
        QSettings().setValue("buntinglabs-kue/auth_token", key)
        self.toggleKue()

    # ================================================
    # AI Management (inputs and outputs)
    # ================================================

    def createKueContext(self):
        project_crs = QgsProject.instance().crs()
        layers = QgsProject.instance().mapLayers().values()
        vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
        raster_layers = [layer for layer in layers if isinstance(layer, QgsRasterLayer)]

        # Transform bounding box to EPSG:4326 if needed
        qgis_bbox = self.iface.mapCanvas().extent()
        if project_crs != QgsCoordinateReferenceSystem("EPSG:4326"):
            try:
                transform = QgsCoordinateTransform(project_crs, QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance())
                qgis_bbox = transform.transformBoundingBox(qgis_bbox)
            except Exception as e:
                print(f"Failed to transform bounding box to EPSG:4326: {e}")
                pass

        return {
            "projection": project_crs.authid(),
            "locale": QSettings().value('locale/userLocale'),
            "bbox": [
                qgis_bbox.xMinimum(),
                qgis_bbox.yMinimum(),
                qgis_bbox.xMaximum(),
                qgis_bbox.yMaximum()
            ],
            "vector_layers": [
                {
                    "layer_name": layer.name(),
                    "source": layer.source(),
                    "visible": is_layer_visible(layer),
                    "layer_type": QgsWkbTypes.displayString(layer.wkbType()),
                    "symbology": self.getLayerSymbology(layer),
                    "num_features": layer.featureCount(),
                    # For now, give only 1 feature (if present) with islice
                    "attribute_example": [{
                        str(field.name()): str(feature[field.name()]) 
                        for field in layer.fields()
                        if field.name() in feature.fields().names()
                    } for feature in islice(layer.getFeatures(), 1)]
                }
                for layer in vector_layers
            ],
            "raster_layers": [
                {
                    "layer_name": layer.name(),
                    "visible": is_layer_visible(layer)
                }
                for layer in raster_layers
            ]
        }

    def getLayerSymbology(self, layer):
        renderer = layer.renderer()
        if isinstance(renderer, QgsFillSymbol):
            symbol = renderer.symbol()
            return {
                "type": "fill",
                "color": symbol.color().name(),
                "opacity": symbol.opacity()
            }
        else:
            return {"type": "unknown"}

    def setProjection(self, projection_action):
        QgsProject.instance().setCrs(
            QgsCoordinateReferenceSystem(f"EPSG:{projection_action['epsg_code']}")
        )

    def handleKueResponse(self, data):
        for action in data.get('actions', []):
            # Sometimes they get put in the same dict (bad, but whatever)
            if action.get('add_xyz_layer'):
                self.addXYZLayer(action['add_xyz_layer'])
            if action.get('add_wfs_layer'):
                self.addWFSLayer(action['add_wfs_layer'])
            if action.get('add_wms_layer'):
                self.addWMSLayer(action['add_wms_layer'])
            if action.get('add_cloud_vector_layer'):
                self.addCloudVectorLayer(action['add_cloud_vector_layer'])
            if action.get('add_arcgis_rest_server_layer'):
                self.addArcGISFeatureServerLayer(action['add_arcgis_rest_server_layer'])
            if action.get('set_vector_single_symbol'):
                self.setVectorSingleSymbology(action['set_vector_single_symbol'])
            if action.get('set_vector_categorized_symbol'):
                self.setVectorCategorizedSymbol(action['set_vector_categorized_symbol'])
            if action.get('set_vector_graduated_symbol'):
                self.setVectorGraduatedSymbol(action['set_vector_graduated_symbol'])
            if action.get('zoom_to_bounding_box'):
                self.zoomToBoundingBox(action['zoom_to_bounding_box'])
            if action.get('set_vector_labels'):
                self.setVectorLabels(action['set_vector_labels'])
            if action.get('set_layer_visibility'):
                self.setLayerVisibility(action['set_layer_visibility'])
            if action.get('suggest_pyqgis_code'):
                self.suggestPyQGISCode(action['suggest_pyqgis_code'])
            if action.get('set_vector_layer_subset_string'):
                self.setVectorLayerSubsetString(action['set_vector_layer_subset_string'])
            if action.get('chat'):
                self.text_dock_widget.addMessage({"role": "assistant", "msg": action['chat']['message']})
                # self.updateChatDisplay()
            if action.get('geoprocessing'):
                # Give system message
                # Get display name for geoprocessing algorithm
                for alg in QgsApplication.processingRegistry().algorithms():
                    if alg.id() == action['geoprocessing']['id']:
                        self.text_dock_widget.addMessage({"role": "geoprocessing", "msg": f"Running {alg.displayName()}..."})
                        # self.updateChatDisplay()
                        break

                processing.runAndLoadResults(
                    action['geoprocessing']['id'],
                    action['geoprocessing']['parameters']
                )
            if action.get('display_datasets'):
                self.displayDatasets(action['display_datasets'])
            if action.get('set_projection'):
                self.setProjection(action['set_projection'])

    def displayDatasets(self, action):
        message = action['message']
        datasets = action['datasets']
        html = f"{message}<br>"
        for dataset in datasets:
            html += f'<div style="padding: 8px;"><a href="{dataset["url"]}" style="color: #0066cc; text-decoration: none;" onmouseover="this.style.color=\'#003366\'" onmouseout="this.style.color=\'#0066cc\'">{dataset["title"]}</a><br><span style="color: #000000;">{dataset["description"]}</span></div>'

        self.text_dock_widget.addMessage({"role": "assistant", "msg": html})
        # self.updateChatDisplay()

    def setVectorLabels(self, label_action):
        layers = QgsProject.instance().mapLayersByName(label_action['layer_name'])
        if not layers:
            return
        layer = layers[0]
        if isinstance(layer, QgsVectorLayer):
            label_settings = QgsPalLayerSettings()
            label_settings.fieldName = label_action['attribute_name']
            label_settings.enabled = True

            text_format = QgsTextFormat()
            text_format.setSize(label_action.get('font_size', 10))
            if label_action['text_buffer_size_mm'] > 0:
                buffer_settings = QgsTextBufferSettings()
                buffer_settings.setEnabled(True)
                buffer_settings.setSize(label_action['text_buffer_size_mm'])
                buffer_settings.setColor(QColor(255, 255, 255))
                buffer_settings.setOpacity(0.8)
                text_format.setBuffer(buffer_settings)
            label_settings.setFormat(text_format)
            layer_settings = QgsVectorLayerSimpleLabeling(label_settings)
            layer.setLabelsEnabled(True)
            layer.setLabeling(layer_settings)
            layer.triggerRepaint()

    def zoomToBoundingBox(self, bbox):
        source_crs = QgsCoordinateReferenceSystem('EPSG:4326')
        rectangle = QgsRectangle(bbox['xmin'], bbox['ymin'], bbox['xmax'], bbox['ymax'])
        dest_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        try:
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
            transformed_rectangle = transform.transformBoundingBox(rectangle)
            self.iface.mapCanvas().setExtent(transformed_rectangle)
            self.iface.mapCanvas().refresh()
        except Exception as e:
            self.handleKueError(f"Failed to zoom to bounding box: {e}")

    def openAttributeTable(self, layer_name):
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            return
        layer = layers[0]
        if layer and isinstance(layer, QgsVectorLayer):
            self.iface.openAttributeTable(layer)

    def setVectorLayerSubsetString(self, subset_action):
        layer = QgsProject.instance().mapLayersByName(subset_action['layer_name'])[0]
        if layer and isinstance(layer, QgsVectorLayer):
            if not layer.setSubsetString(subset_action['subset_string']):
                self.text_dock_widget.addMessage({"role": "error", "msg": "Failed to set subset string", "has_button": False})
            else:
                self.text_dock_widget.addMessage({"role": "assistant", "msg": f"{subset_action['layer_name']}: {subset_action['subset_string']}", "has_button": False})
            layer.triggerRepaint()

    def setVectorSingleSymbology(self, symbology_action):
        layer = QgsProject.instance().mapLayersByName(symbology_action['layer_name'])[0]
        if layer and isinstance(layer, QgsVectorLayer):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(symbology_action['color']))
            symbol.setOpacity(symbology_action['opacity'])
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

    def setVectorCategorizedSymbol(self, symbology_action):
        layer = QgsProject.instance().mapLayersByName(symbology_action['layer_name'])[0]
        if layer and isinstance(layer, QgsVectorLayer):
            field_name = symbology_action['field_name']
            unique_values = layer.uniqueValues(layer.fields().indexFromName(field_name))
            categories = []

            for value in unique_values:
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                if symbology_action['colormap'] == 'random':
                    symbol.setColor(QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
                # TODO other color maps
                symbol.setOpacity(symbology_action['opacity'])
                category = QgsRendererCategory(value, symbol, str(value))
                categories.append(category)

            renderer = QgsCategorizedSymbolRenderer(field_name, categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

    def setVectorGraduatedSymbol(self, symbology_action):
        layer = QgsProject.instance().mapLayersByName(symbology_action['layer_name'])[0]
        if layer and isinstance(layer, QgsVectorLayer):
            field_name = symbology_action['field_name']
            classes = symbology_action['classes']

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setOpacity(symbology_action['opacity'])

            # Create graduated renderer
            renderer = QgsGraduatedSymbolRenderer(field_name)
            renderer.setSourceSymbol(symbol.clone())

            # Calculate class breaks using equal interval
            field_index = layer.fields().indexFromName(field_name)
            min_val, max_val = layer.minimumAndMaximumValue(field_index)
            if min_val is None or max_val is None:
                self.handleKueError(f"Can't read min/max values for {layer.name()}, try re-exporting to a Shapefile.")
                return
            interval = (max_val - min_val) / classes

            # Choose one of 4 diverging color ramps randomly
            color_ramps = [
                [QColor(208,28,139), QColor(77,172,38)],   # Pink-Green
                [QColor(184,55,115), QColor(53,151,143)],  # Purple-Teal
                [QColor(230,97,1), QColor(94,113,106)],    # Orange-Gray
                [QColor(214,47,39), QColor(33,102,172)]    # Red-Blue
            ]
            start_color, end_color = random.choice(color_ramps)

            # Create class breaks and assign symbols
            for i in range(classes):
                lower = min_val + (interval * i)
                upper = min_val + (interval * (i + 1))

                # Calculate interpolated color
                t = i / (classes - 1) if classes > 1 else 0
                r = int(start_color.red() + (end_color.red() - start_color.red()) * t)
                g = int(start_color.green() + (end_color.green() - start_color.green()) * t)
                b = int(start_color.blue() + (end_color.blue() - start_color.blue()) * t)

                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                symbol.setColor(QColor(r, g, b))
                symbol.setOpacity(symbology_action['opacity'])

                range_label = f'{lower:.2f} - {upper:.2f}'
                renderer.addClassRange(QgsRendererRange(lower, upper, symbol, range_label))

            layer.setRenderer(renderer)
            layer.triggerRepaint()

    def addXYZLayer(self, xyz_action):
        uri = f"type=xyz&url={xyz_action['url']}"
        layer = QgsRasterLayer(uri, xyz_action['name'], "wms")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)

    def addWFSLayer(self, wfs_action):
        layer = QgsVectorLayer(wfs_action['url'], wfs_action['name'], "WFS")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)

    def addWMSLayer(self, wms_action):
        uri = f"url={wms_action['url']}"
        layer = QgsRasterLayer(uri, wms_action['name'], "wms")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)

    def addArcGISFeatureServerLayer(self, arcgis_feature_server_action):
        print('adding rest server')
        uri = QgsDataSourceUri()
        uri.setParam('crs', 'EPSG:3857')
        uri.setParam('url', arcgis_feature_server_action['url'])
        layer = QgsVectorLayer(uri.uri(), arcgis_feature_server_action['name'], "arcgisfeatureserver")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
        else:
            print('not valid')

    def suggestPyQGISCode(self, code_action):
        self.text_dock_widget.addMessage({"role": "assistant", "msg": code_action['code'], "has_button": True})

    def addCloudVectorLayer(self, cloud_vector_action):
        layer = QgsVectorLayer(f"/vsicurl/{cloud_vector_action['url']}", cloud_vector_action['name'], "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)

    def setLayerVisibility(self, visibility_action):
        layers = QgsProject.instance().mapLayersByName(visibility_action['layer_name'])
        if not layers:
            return
        layer = layers[0]
        tree_layer = QgsProject.instance().layerTreeRoot().findLayer(layer)
        if tree_layer:
            tree_layer.setItemVisibilityChecked(visibility_action['visible'])
            self.iface.mapCanvas().refresh()

    def handleKueError(self, msg):
        self.text_dock_widget.addMessage({"role": "error", "msg": msg, "has_button": False})

    def onEnterClicked(self, text: str, history: list[str]):
        history_str = '\n'.join(history)[-2048:]

        kue_task = KueTask(text, self.createKueContext(), history_str)
        kue_task.responseReceived.connect(self.handleKueResponse)
        kue_task.errorReceived.connect(self.handleKueError)
        QgsApplication.taskManager().addTask(kue_task)
        self.task_trash.append(kue_task)

        self.text_dock_widget.addMessage({"role": "user", "msg": text, "has_button": False})
        # self.updateChatDisplay()

def is_layer_visible(layer):
    return QgsProject.instance().layerTreeRoot().findLayer(layer).isVisible()
