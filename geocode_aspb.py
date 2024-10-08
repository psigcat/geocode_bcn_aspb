from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from PyQt5.QtWidgets import QMessageBox
from qgis.core import QgsProject, QgsVectorLayer, QgsProcessingFeedback
from PyQt5.QtGui import QDoubleValidator
import processing
# Import the code for the dialog
from .geocode_aspb_db import GisAspbDB
from .geocode_aspb_dialog import geocode_aspbDialog
import os.path
import json
#from geocodeaspb_utils import get_metadata_parameter


class geocode_aspb:
    """QGIS Plugin Implementation.º"""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        self.geocode_aspb_db = None
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'geocode_aspb_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&geocode_aspb')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('geocode_aspb', message)


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
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = os.path.join(self.plugin_dir, 'img', 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Importar capas, calculs similituds'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&geocode_aspb'), action)
            self.iface.removeToolBarIcon(action)
        
        # Close DDBB
        if self.geocode_aspb_db:
            self.geocode_aspb_db.TancarBaseDades()
        self.geocode_aspb_db = None
        del self.geocode_aspb_db


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = geocode_aspbDialog()
            # Connect the import button to the import function
            self.dlg.import_button.clicked.connect(self.importLayer)
            # Connect the signal currentIndexChanged of comboBox_selectTable to charge elements og the table
            self.dlg.comboBox_selectTable.currentIndexChanged.connect(self.chargeTableElements)
            # Connect the cancel button to the cancel function
            self.dlg.cancelButton.clicked.connect(self.cleanFormClac)
            # Connect the acept button to the calc function
            self.dlg.aceptButton.clicked.connect(self.calcSimilarity)
            # Set up the validator for spin_coef
            # validator = QDoubleValidator(0.1, 0.999999, 6, self.dlg)
            # validator.setNotation(QDoubleValidator.StandardNotation)
            # self.dlg.spin_coef.setValidator(validator)

        # Call function 'getLayersProjectActive()'
        self.getLayersProjectActive()

        # Connect DDBB
        self.geocode_aspb_db = GisAspbDB(self.plugin_dir)
        self.geocode_aspb_db.LlegirConfig()
        self.db = self.geocode_aspb_db.ObrirBaseDades()
        if self.geocode_aspb_db.bd_open:
            if not self.geocode_aspb_db.SetSearchPath():
                self.Avis(self.geocode_aspb_db.last_error)
                return
            self.param = self.geocode_aspb_db.param
            self.getTablesCalc()
        else:
            self.Avis(self.geocode_aspb_db.last_error)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()


    def getLayersProjectActive(self):
            """ Populate the comboBox with the current layers in QGIS. """
            # Clear existing items
            self.dlg.comboBox_selecLayer.clear()
            self.dlg.comboBox_selecLayer.addItem("","")

            # Get the list of layers
            layers = QgsProject.instance().mapLayers().values()
            for layer in layers:
                self.dlg.comboBox_selecLayer.addItem(layer.name(), layer.id())

    def importLayer(self):
        """ Check mandatory fields and import the layer to DDBB. """

        # Check mandatory fields
        if self.dlg.comboBox_selecLayer.currentText() == "":
            self.Avis("S'ha de seleccionar una capa del projecte")
            return
        if self.dlg.lineEdit_nameTable.text() == "":
            self.Avis("S'ha de indicar un nom per la taula a importa")
            return

        layer_name = self.dlg.comboBox_selecLayer.currentText()
        table_name = self.dlg.lineEdit_nameTable.text()
        layer = QgsProject.instance().mapLayersByName(layer_name)[0]

        if not isinstance(layer, QgsVectorLayer):
            self.Avis("La capa seleccionada no es una capa vectorial.")
            return

        if not self.geocode_aspb_db or not self.geocode_aspb_db.bd_open:
            self.Avis("La base de dades no està oberta.")
            return

        # Get database connection parameters
        db_params = self.geocode_aspb_db.param
        database = db_params.get('database', '')
        schema = db_params.get('schema', '')

        if not database or not schema:
            self.Avis("Falta la definició de la base de dades i del schema.")
            return

        # Use processing algorithm to import layer into PostgreSQL/PostGIS
        alg_params = {
            'INPUT': layer,
            'DATABASE': database,
            'SCHEMA': schema,
            'TABLENAME': table_name,
            'PRIMARY_KEY': 'id',
            'GEOMETRY_COLUMN': 'geom',
            'ENCODING': 'UTF-8',
            'OVERWRITE': True,
            'CREATEINDEX': True,
            'DROP_STRING_LENGTH': False,
            'FORCE_SINGLEPART': False,
            'LOWERCASE_NAMES': True
        }
        

        feedback = QgsProcessingFeedback()
        try:
            processing.run('native:importintopostgis', alg_params, feedback=feedback)
            self.Avis("Capa importada correctament a la base de dades.", "I")
            self.cleanFormImport()
            self.getTablesCalc()
        except Exception as e:
            self.Avis(f"Error en importar la capa: {str(e)}", "C")


    def getTablesCalc(self):
        """ Get tables from the similarity schema and put them in the comobobox """

        self.dlg.comboBox_selectTable.clear()
        
        sql = ("SELECT table_name FROM information_schema.tables WHERE table_schema = 'similitud' "
               "AND table_type = 'BASE TABLE';")

        rows = self.geocode_aspb_db.get_rows(sql)
        if rows is None:
            msg= f"Error en la carega de les taules\n\n{self.geocode_aspb_db.last_error}"
            self.Avis(msg) if self.geocode_aspb_db.last_error else self.show_info(self.geocode_aspb_db.last_msg)
            return
        
        self.dlg.comboBox_selectTable.addItem("","")
        for row in rows:
            nombre = row[0]
            self.dlg.comboBox_selectTable.addItem(nombre)


    def chargeTableElements(self):
        """ Charge table elements when a table is selected """

        if self.dlg.comboBox_selectTable.currentText() == "":
            return

        # Clear combobox 
        self.dlg.comboBox_tipos.clear()
        self.dlg.comboBox_nomVia.clear()
        self.dlg.comboBox_numPortal.clear()

        nombre_tabla = self.dlg.comboBox_selectTable.currentText()
        sql = (f"SELECT column_name FROM information_schema.columns WHERE table_schema = 'similitud' "
               f"AND table_name = '{nombre_tabla}';")

        rows = self.geocode_aspb_db.get_rows(sql)
        if rows is None:
            msg= f"Error en la carega dels elements de la tula\n\n{self.geocode_aspb_db.last_error}"
            self.Avis(msg) if self.geocode_aspb_db.last_error else self.show_info(self.geocode_aspb_db.last_msg)
            return
        
        self.dlg.comboBox_tipos.addItem("","")
        self.dlg.comboBox_nomVia.addItem("","")
        self.dlg.comboBox_numPortal.addItem("","")
        for row in rows:
            nombre = row[0]
            self.dlg.comboBox_tipos.addItem(nombre)
            self.dlg.comboBox_nomVia.addItem(nombre)
            self.dlg.comboBox_numPortal.addItem(nombre) 


    def calcSimilarity(self):
        """ Calculate the similarity and add the geometry """

        # Check selected table
        if self.dlg.comboBox_selectTable.currentText() == "":
            self.Avis("Selecciona una taula per poder calcular la similitud")
            return
        nombre_tabla = self.dlg.comboBox_selectTable.currentText()
        carrerer_tabla = self.geocode_aspb_db.get_metadata_parameter("app", "carrerer")

        # Initialize clauses
        tipo_clause = ""
        tipo_compare_clause = ""
        tipo_where_clause = ""

        # Check if comboBox_tipos has an item selected
        if self.dlg.comboBox_tipos.currentText() != "":
            tipo = self.dlg.comboBox_tipos.currentText()
            self.chekTipos(tipo, nombre_tabla)
            tipo_clause = f"c.{tipo} || ' ' || "
            tipo_compare_clause = f"c.{tipo} || ' ' || "
            tipo_where_clause = f" AND c.{tipo} IS NOT NULL"

        # Check if comboBox_nomVia has an item selected
        if self.dlg.comboBox_nomVia.currentText() != "":
            nomVia = self.dlg.comboBox_nomVia.currentText()
        else:
            self.Avis("La opció de nom via és obligatòria")
            return

        # Initialize clauses
        numPortal_clause = ""
        numPortal_compare_clause = ""
        numPortal_where_clause = ""

        # Check if comboBox_numPortal has an item selected
        if self.dlg.comboBox_numPortal.currentText() != "":
            numPortal = self.dlg.comboBox_numPortal.currentText()
            numPortal_clause = f" || ', ' || c.{numPortal}"
            numPortal_compare_clause = f" || ', ' || c.{numPortal}"
            numPortal_where_clause = f" AND c.{numPortal} IS NOT NULL"

        # Check if coef is a correct input
        coeficient = self.dlg.spin_coef.value()
        try:
            coef = float(coeficient)
            if coef < 0.1 or coef >= 1:
                self.Avis("El coeficient ha d'estar entre 0.1 i 1")
                return
        except ValueError:
            self.Avis("El coeficient ha de ser un número vàlid entre 0.1 i 1")
            return

        sql = (f"CREATE EXTENSION IF NOT EXISTS unaccent;"
            f"CREATE EXTENSION IF NOT EXISTS pg_trgm;"
            f"ALTER TABLE similitud.{nombre_tabla} ADD COLUMN IF NOT EXISTS geom geometry(Point, 25831);"
            f"ALTER TABLE similitud.{nombre_tabla} ADD COLUMN IF NOT EXISTS similarity real;"
            f"UPDATE similitud.{nombre_tabla} AS c SET (geom, similarity) = ("
            f"SELECT a.geom, similarity("
            f"({tipo_clause} unaccent(COALESCE(c.{nomVia}, '')) {numPortal_clause}), "
            f"(unaccent(COALESCE(a.nom_via, '')) || ', ' || COALESCE(a.literal, ''))) " 
            f"FROM {carrerer_tabla} AS a WHERE similarity("
            f"({tipo_compare_clause} unaccent(COALESCE(c.{nomVia}, '')) {numPortal_compare_clause}), "
            f"(unaccent(COALESCE(a.nom_via, '')) || ', ' || COALESCE(a.literal, ''))) > {coef} "
            f"ORDER BY similarity("
            f"({tipo_compare_clause} unaccent(COALESCE(c.{nomVia}, '')) {numPortal_compare_clause}), "
            f"(unaccent(COALESCE(a.nom_via, '')) || ', ' || COALESCE(a.literal, ''))) DESC LIMIT 1)" 
            f"WHERE c.geom IS NULL AND c.{nomVia} IS NOT NULL "
            f"{tipo_where_clause} "
            f"{numPortal_where_clause};")
        
        success = self.geocode_aspb_db.exec_sql(sql)
        if not success:
            msg = f"Error \n\n{self.geocode_aspb_db.last_error}"
            self.Avis(msg) if self.geocode_aspb_db.last_error else self.show_info(self.geocode_aspb_db.last_msg)
            print(self.geocode_aspb_db.last_error)
            return
        
        print("Query executed successfully.")
        self.Avis("El clacul a finalitzat", "i")
        self.cleanFormClac()


    def chekTipos(self, colTipo, nombre_tabla):
        """ Check and change the type like adrecces """
        
        file_path = os.path.join(os.path.dirname(__file__), 'diccionarioTipos.json')

        try: 
            diccionarioTipos = self.cargar_diccionarioTipos(file_path)
        except FileNotFoundError as e:
            self.Avis(str(e))
            return

        sql = (f"SELECT id, {colTipo} FROM {nombre_tabla};")
        
        rows = self.geocode_aspb_db.get_rows(sql)
        if rows is None:
            msg= f"Error en la carega de la columna de tipus\n\n{self.geocode_aspb_db.last_error}"
            self.Avis(msg) if self.geocode_aspb_db.last_error else self.show_info(self.geocode_aspb_db.last_msg)
            return 
        
        cambios = []
        for row in rows:
            id = row[0]
            tipo_actual = row[1]

            if isinstance(tipo_actual, str):  # Verificar que tipo_actual es una cadena
                tipo_nuevo = diccionarioTipos.get(tipo_actual.lower())  # Usamos lower() para evitar problemas de mayúsculas

                if tipo_nuevo:
                    cambios.append((tipo_nuevo, id))

        for nuevo_valor, id in cambios:
            sql = f"UPDATE {nombre_tabla} SET {colTipo} = '{nuevo_valor}' WHERE id = {id};"
            success = self.geocode_aspb_db.exec_sql(sql)

            if not success:
                msg = f"Error al actualitzar el tipus de via amb id: {id}\n\n{self.geocode_aspb_db.last_error}"
                self.Avis(msg) if self.geocode_aspb_db.last_error else sel.show_info(self.geocode_aspb_db.last_msg)
        
        print("actualizacion completada")


    def cargar_diccionarioTipos(self, file_path):
        """ Load type dictionary  """

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"L'arixiu {file_path} no existeix")

        with open(file_path, 'r', encoding='utf-8') as f:
            diccionarioTipos = json.load(f)

        if not isinstance(diccionarioTipos, dict):
            raise ValueError(f"El archivo {file_path} no contiene un diccionario")

        return diccionarioTipos


    def cleanFormClac(self):
        """ Clean the calc form """

        self.getTablesCalc() 
        self.dlg.comboBox_tipos.setCurrentIndex(0)
        self.dlg.comboBox_nomVia.setCurrentIndex(0)
        self.dlg.comboBox_numPortal.setCurrentIndex(0)
        self.dlg.spin_coef.clear()


    def cleanFormImport(self):
        """ Clean the import form """

        self.dlg.comboBox_selecLayer.setCurrentIndex(0)
        self.dlg.lineEdit_nameTable.setText("")


    # General functions

    def Avis(self, t, av="W"):
        """ Finestra missatges
        :param t: mensaje de texto para el quadro de dialogo
        :param av: tipo de aviso con valor predeterminado w
        :return: ejecución del mensaje
        """

        m = QMessageBox()
        m.setText(t) #Establece el texto en la ventana de dialogo
        if av == "P": #Si es pregunta, se configura el cuadro de mensage para realizar la pregunta con el titulo y dos botones de si y no
            m.setIcon(QMessageBox.Information)
            m.setWindowTitle("Pregunta")
            m.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            b1 = m.button(QMessageBox.Yes)
            b1.setText("Sí")
            b2 = m.button(QMessageBox.No)
            b2.setText("No")
        else:
            if av == "W": # Si es Warning (Advertencia), se canvia el iciono a uno de advertencia y especificamos el titulo "Atenció"
                m.setIcon(QMessageBox.Warning)
                z="Atenció"
            elif av == "C": #Si es Critical, se canvia el icono y especificamos el titulo como "Error"
                m.setIcon(QMessageBox.Critical)
                z="Error"
            else: #el resto de ventanas seran de informacion se canvia el icono y el titulo a "aviso"
                m.setIcon(QMessageBox.Information)
            m.setWindowTitle("Avís")
            m.setStandardButtons(QMessageBox.Ok)
            b = m.button(QMessageBox.Ok)
            b.setText("Tancar")

        return m.exec_()


    def show_info(self, text, message_level=0, duration=10, title=""):
        """ Displays an information message """

        self.iface.messageBar().pushMessage(title, text, message_level, duration)