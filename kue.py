# Copyright 2024 Bunting Labs, Inc.

import os
import random
import secrets
import string

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
    QgsRendererCategory, QgsRasterLayer
)
from qgis import processing
from qgis.core import QgsFillSymbol

from .kue_task import KueTask
from .kue_messages import KUE_INTRODUCTION_MESSAGES

class KuePlugin:

    def __init__(self, iface):
        self.iface = iface
        self.settings = QSettings()

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

        self.textbox = None
        self.text_dock_widget = None

        # Load the greeting message 
        locale = QSettings().value('locale/userLocale', 'en_US')
        lang = locale[2:] if isinstance(locale, str) and len(locale) > 2 else 'en'
        starter_messages = KUE_INTRODUCTION_MESSAGES.get(
            lang,
            KUE_INTRODUCTION_MESSAGES['en']
        )
        self.context_messages = [{
            "role": "assistant", "msg": msg
        } for msg in starter_messages]

        self.task_trash = []

    # ================================================
    # GUI management
    # ================================================

    def initGui(self):
        self.iface.mainWindow().addAction(self.kue_action)
        self.kue_action.triggered.connect(self.toggleKue)
        self.iface.addToolBarIcon(self.kue_action)

    def unload(self):
        self.iface.removeToolBarIcon(self.kue_action)

    def toggleKue(self):
        if self.text_dock_widget is None:
            self.text_dock_widget = QDockWidget("Kue", self.iface.mainWindow())

            # User needs to authenticate to access the cloud services
            user_auth_token = self.settings.value("buntinglabs-kue/auth_token", "")

            if not user_auth_token:
                auth_widget = QWidget()
                auth_layout = QVBoxLayout()
                auth_layout.setAlignment(Qt.AlignVCenter)

                title = QLabel("<h2>Kue</h2>")
                title.setContentsMargins(0, 0, 0, 10)
                description = QLabel("Kue is an embedded AI assistant inside QGIS. It can read and edit your project, using cloud AI services to do so (LLMs).")
                description.setWordWrap(True)
                description.setContentsMargins(0, 0, 0, 10)
                description.setMinimumWidth(300)
                pricing = QLabel("Using Kue requires a subscription of $19/month (first month free). This allows us to build useful AI tools.")
                pricing.setWordWrap(True)
                pricing.setContentsMargins(0, 0, 0, 10)
                pricing.setMinimumWidth(300)
                login_button = QPushButton("Log In")
                login_button.setFixedWidth(280)
                login_button.setStyleSheet("QPushButton { background-color: #0d6efd; color: white; border: none; padding: 8px; border-radius: 4px; } QPushButton:hover { background-color: #0b5ed7; }")
                login_button.clicked.connect(self.authenticateUser)

                auth_layout.addWidget(title)
                auth_layout.addWidget(description)
                auth_layout.addWidget(pricing)
                auth_layout.addWidget(login_button)
                auth_widget.setLayout(auth_layout)

                self.text_dock_widget.setWidget(auth_widget)
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self.text_dock_widget)
            else:
                self.textbox = QLineEdit()
                self.textbox.returnPressed.connect(self.onEnterClicked)

                def handleKeyPress(e):
                    if e.key() == Qt.Key_Up:
                        user_messages = [msg for msg in self.context_messages if msg['role'] == 'user']
                        if user_messages:
                            self.textbox.setText(user_messages[-1]['msg'])
                    else:
                        QLineEdit.keyPressEvent(self.textbox, e)
                self.textbox.keyPressEvent = handleKeyPress

                self.enter_button = QPushButton("Enter")
                self.enter_button.setFixedSize(50, 20)
                self.enter_button.clicked.connect(self.onEnterClicked)

                layout = QVBoxLayout()
                self.chat_display = QLabel()
                self.chat_display.setWordWrap(True)
                self.chat_display.setAlignment(Qt.AlignBottom)
                self.chat_display.setOpenExternalLinks(True)
                self.chat_display.setTextInteractionFlags(Qt.TextBrowserInteraction)

                scroll_area = QScrollArea()
                scroll_area.setFrameShape(QFrame.NoFrame)
                scroll_area.setWidgetResizable(True)
                scroll_area.setWidget(self.chat_display)
                layout.addWidget(scroll_area)

                h_layout = QHBoxLayout()
                h_layout.addWidget(self.textbox)
                h_layout.addWidget(self.enter_button)
                layout.addLayout(h_layout)

                self.text_widget = QWidget()
                self.text_widget.setLayout(layout)

                self.text_dock_widget.setWidget(self.text_widget)
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self.text_dock_widget)

                self.updateChatDisplay()
        else:
            if self.text_dock_widget is not None:
                self.iface.removeDockWidget(self.text_dock_widget)
                self.text_dock_widget = None
                self.text_widget = None
                self.textbox = None

    def handleLinkClick(self, url):
        # Handle link clicks - url is a string containing the clicked URL
        QDesktopServices.openUrl(QUrl(url))

    def updateChatDisplay(self):
        messages = "".join(
            f"<p style='text-align: {'right' if msg['role'] == 'user' else 'left'}; "
            f"color: {'red' if msg['role'] == 'error' else '#1E3E62' if msg['role'] == 'system' else '#000'}; "
            f"{'font-style:italic;' if msg['role'] in ['system', 'error'] else ''}'>"
            f"{msg['msg']}</p>"
            for msg in self.context_messages
        )
        self.chat_display.setText(messages)
        
        # Scroll to the bottom
        scroll_area = self.chat_display.parent()
        if isinstance(scroll_area, QScrollArea):
            scroll_bar = scroll_area.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())

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
        layers = QgsProject.instance().mapLayers().values()
        vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]

        return {
            "projection": QgsProject.instance().crs().authid(),
            "locale": QSettings().value('locale/userLocale'),
            "vector_layers": [
                {
                    "layer_name": layer.name(),
                    "source": layer.source(),
                    "layer_type": QgsWkbTypes.displayString(layer.wkbType()),
                    "symbology": self.getLayerSymbology(layer),
                    "num_features": layer.featureCount(),
                    "attribute_example": [] if layer.featureCount() == 0 else [{
                        str(field.name()): str(feature[field.name()]) 
                        for field in layer.fields()
                        if field.name() in feature.fields().names()
                    } for feature in [layer.getFeature(0)]]
                }
                for layer in vector_layers
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
            if action.get('set_vector_single_symbol'):
                self.setVectorSingleSymbology(action['set_vector_single_symbol'])
            if action.get('set_vector_categorized_symbol'):
                self.setVectorCategorizedSymbol(action['set_vector_categorized_symbol'])
            if action.get('zoom_to_bounding_box'):
                self.zoomToBoundingBox(action['zoom_to_bounding_box'])
            if action.get('set_vector_labels'):
                self.setVectorLabels(action['set_vector_labels'])
            if action.get('chat'):
                self.context_messages.append({"role": "assistant", "msg": action['chat']['message']})
                self.updateChatDisplay()
            if action.get('geoprocessing'):
                # Give system message
                # Get display name for geoprocessing algorithm
                for alg in QgsApplication.processingRegistry().algorithms():
                    if alg.id() == action['geoprocessing']['id']:
                        self.context_messages.append({"role": "system", "msg": f"Running {alg.displayName()}..."})
                        self.updateChatDisplay()
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

        self.context_messages.append({"role": "assistant", "msg": html})
        self.updateChatDisplay()

    def setVectorLabels(self, label_action):
        layers = QgsProject.instance().mapLayersByName(label_action['layer_name'])
        if not layers:
            return
        layer = layers[0]
        if isinstance(layer, QgsVectorLayer):
            label_settings = QgsPalLayerSettings()
            label_settings.fieldName = label_action['attribute_name']
            label_settings.enabled = True
            if label_action['text_buffer_size_mm'] > 0:
                # Add buffer settings
                text_format = QgsTextFormat()
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
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
        transformed_rectangle = transform.transformBoundingBox(rectangle)
        self.iface.mapCanvas().setExtent(transformed_rectangle)
        self.iface.mapCanvas().refresh()

    def openAttributeTable(self, layer_name):
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            return
        layer = layers[0]
        if layer and isinstance(layer, QgsVectorLayer):
            self.iface.openAttributeTable(layer)

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

    def addCloudVectorLayer(self, cloud_vector_action):
        layer = QgsVectorLayer(f"/vsicurl/{cloud_vector_action['url']}", cloud_vector_action['name'], "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)

    def handleKueError(self, msg):
        self.context_messages.append({"role": "error", "msg": msg})
        self.updateChatDisplay()

    def onEnterClicked(self):
        text = self.textbox.text()

        kue_task = KueTask(text, self.createKueContext())
        kue_task.responseReceived.connect(self.handleKueResponse)
        kue_task.errorReceived.connect(self.handleKueError)
        QgsApplication.taskManager().addTask(kue_task)
        self.task_trash.append(kue_task)

        self.textbox.clear()

        self.context_messages.append({"role": "user", "msg": text})
        self.updateChatDisplay()

