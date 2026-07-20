# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox


class CivilTools:
    """Complemento Civil Tools para QGIS."""

    def __init__(self, iface):
        """
        Constructor del complemento.

        :param iface: Interfaz principal de QGIS.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        self.actions = []
        self.menu = self.tr("&Civil Tools")
        self.toolbar = self.iface.addToolBar("Civil Tools")
        self.toolbar.setObjectName("CivilTools")

        locale = QSettings().value("locale/userLocale", "")[:2]
        locale_path = os.path.join(
            self.plugin_dir,
            "i18n",
            f"civil_tools_{locale}.qm"
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def tr(self, message):
        """Traduce textos del complemento."""
        return QCoreApplication.translate("CivilTools", message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """Crea una acción para el menú y la barra de herramientas."""

        icon = QIcon(icon_path)

        action = QAction(
            icon,
            text,
            parent
        )

        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip:
            action.setStatusTip(status_tip)

        if whats_this:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action
            )

        self.actions.append(action)

        return action

    def initGui(self):
        """Crea el botón y el menú del complemento."""

        icon_path = os.path.join(
            self.plugin_dir,
            "icon.png"
        )

        self.add_action(
            icon_path=icon_path,
            text=self.tr("Civil Tools"),
            callback=self.run,
            parent=self.iface.mainWindow()
        )

    def unload(self):
        """Elimina el botón y el menú al descargar el complemento."""

        for action in self.actions:
            self.iface.removePluginMenu(
                self.menu,
                action
            )

            self.iface.removeToolBarIcon(
                action
            )

        if self.toolbar:
            del self.toolbar

    def run(self):
        """Acción ejecutada al pulsar el botón."""

    def run(self):
        """Convierte una capa de curvas 2D en una capa LineStringZ."""

        from qgis.PyQt.QtWidgets import (
            QMessageBox,
            QInputDialog
        )

        from qgis.core import (
            QgsProject,
            QgsVectorLayer,
            QgsFeature,
            QgsGeometry,
            QgsWkbTypes
        )

        # Buscar capas vectoriales de líneas cargadas
        capas_lineales = [
            capa
            for capa in QgsProject.instance().mapLayers().values()
            if isinstance(capa, QgsVectorLayer)
            and QgsWkbTypes.geometryType(capa.wkbType())
            == QgsWkbTypes.LineGeometry
        ]

        if not capas_lineales:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Civil Tools",
                "No hay capas vectoriales de líneas cargadas."
            )
            return

        # Elegir la capa
        nombres_capas = [capa.name() for capa in capas_lineales]

        nombre_capa, aceptado = QInputDialog.getItem(
            self.iface.mainWindow(),
            "Seleccionar capa",
            "Elegí la capa de curvas de nivel:",
            nombres_capas,
            0,
            False
        )

        if not aceptado:
            return

        origen = capas_lineales[nombres_capas.index(nombre_capa)]

        # Buscar campos numéricos
        campos_numericos = [
            campo.name()
            for campo in origen.fields()
            if campo.isNumeric()
        ]

        if not campos_numericos:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Civil Tools",
                "La capa seleccionada no tiene campos numéricos."
            )
            return

        # Priorizar ELEV
        indice_inicial = 0

        for i, nombre in enumerate(campos_numericos):
            if nombre.upper() == "ELEV":
                indice_inicial = i
                break

        campo_elevacion, aceptado = QInputDialog.getItem(
            self.iface.mainWindow(),
            "Campo de elevación",
            "Elegí el campo que contiene la cota:",
            campos_numericos,
            indice_inicial,
            False
        )

        if not aceptado:
            return

        # Crear capa temporal 3D
        es_multipart = QgsWkbTypes.isMultiType(origen.wkbType())

        tipo_geometria = (
            "MultiLineStringZ"
            if es_multipart
            else "LineStringZ"
        )

        salida = QgsVectorLayer(
            f"{tipo_geometria}?crs={origen.crs().authid()}",
            f"{origen.name()} 3D",
            "memory"
        )

        proveedor = salida.dataProvider()
        proveedor.addAttributes(origen.fields())
        salida.updateFields()

        objetos_nuevos = []
        omitidos = 0

        for objeto in origen.getFeatures():

            valor = objeto[campo_elevacion]

            if valor is None:
                omitidos += 1
                continue

            try:
                z = float(valor)
            except (TypeError, ValueError):
                omitidos += 1
                continue

            geometria = objeto.geometry()

            if geometria is None or geometria.isEmpty():
                omitidos += 1
                continue

            geometria_3d = QgsGeometry(geometria)
            geometria_3d.get().addZValue(z)

            nuevo = QgsFeature(salida.fields())
            nuevo.setAttributes(objeto.attributes())
            nuevo.setGeometry(geometria_3d)

            objetos_nuevos.append(nuevo)

        if not objetos_nuevos:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Civil Tools",
                "No se pudo crear ninguna curva 3D."
            )
            return

        proveedor.addFeatures(objetos_nuevos)
        salida.updateExtents()

        QgsProject.instance().addMapLayer(salida)

        QMessageBox.information(
            self.iface.mainWindow(),
            "Civil Tools",
            (
                "Proceso terminado correctamente.\n\n"
                f"Capa creada: {salida.name()}\n"
                f"Curvas convertidas: {len(objetos_nuevos)}\n"
                f"Curvas omitidas: {omitidos}\n\n"
                "La capa creada es temporal."
            )
        )