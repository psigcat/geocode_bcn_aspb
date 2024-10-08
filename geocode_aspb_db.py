import os
import configparser

from PyQt5.QtSql import QSqlDatabase, QSqlQuery


class GeocodeAspbDB:

	def __init__(self, plugin_dir):

		self.plugin_dir = plugin_dir
		self.param = {}
		self.db = None
		self.obert = False
		self.bd_open = False
		self.last_error = None
		self.last_msg = None
		self.num_fields = None
		self.num_records = None


	def LlegirConfig(self):
		""" llegir arxiu configuracio """

		# temporary fix to save params from metadata.txt
		self.param = {
			"host": self.get_metadata_parameter("app", "host"),
			"database": self.get_metadata_parameter("app", "database"),
			"port": self.get_metadata_parameter("app", "port"),
			"user": self.get_metadata_parameter("app", "user"),
			"password": self.get_metadata_parameter("app", "password"),
			"service": self.get_metadata_parameter("app", "service"),
			"schema": self.get_metadata_parameter("app", "schema")
		}
		if self.param["schema"]:
			self.param["search_path"] = self.param["schema"]


	def get_metadata_parameter(self, section="general", parameter="version", file="metadata.txt"):
		""" Get parameter value from Metadata """

		# Check if metadata file exists
		metadata_file = os.path.join(self.plugin_dir, file)
		if not os.path.exists(metadata_file):
			show_warning(f"No s'ha trobat l'arxiu de metadades: {metadata_file}")
			return None

		value = None
		try:
			metadata = configparser.ConfigParser()
			metadata.read(metadata_file)
			value = metadata.get(section, parameter)
		except Exception as e:
			show_warning(e)
		finally:
			return value


	def ObrirBaseDades(self):
		""" Obrir base de dades servidor """

		if self.bd_open:
			return self.db

		if self.param["host"] == "" and self.param["service"] == "":
			self.last_error = "No s'ha definit ni host ni service"
			return None

		self.db = QSqlDatabase.addDatabase("QPSQL", self.param['database'])
		if self.param["service"] == "":
			self.db.setHostName(self.param["host"])
			self.db.setDatabaseName(self.param["database"])
			self.db.setUserName(self.param["user"])
			self.db.setPassword(self.param["password"])
			self.db.setPort(int(self.param["port"]))
		else:
			self.db.setConnectOptions(f"service={self.param['service']}")
		self.db.open()
		if self.db.isOpen() == 0:
			self.last_error = f"No s'ha pogut obrir la Base de Dades del servidor\n\n{self.db.lastError().text()}"
			return None

		self.bd_open = True
		return self.db


	def TancarBaseDades(self):
		""" Tancar base de dades servidor """

		if not self.bd_open:
			return True
		self.db.close()
		self.bd_open = False
		return True


	def SetSearchPath(self):

		sql = f"SET search_path = {self.param['search_path']}, public, topology;"
		query = QSqlQuery(self.db)
		if not query.exec(sql):
			self.last_error = f"Error a l'actualitzar paràmetre search_path: {query.lastError().text()}"
			return False
		return True


	def reset_info(self):
		""" Reset query information values """

		self.last_error = None
		self.last_msg = None
		self.num_fields = None
		self.num_records = None


	def exec_sql(self, sql):
		""" Execute SQL (Insert or Update) """

		self.reset_info()
		query = QSqlQuery(self.db)
		status = query.exec(sql)
		if not status:
			self.last_error = query.lastError().text()
		return status


	def get_rows(self, sql):
		""" Execute SQL (Select) and return rows """

		self.reset_info()
		query = QSqlQuery(self.db)
		status = query.exec(sql)
		if not status:
			self.last_error = query.lastError().text()
			return None
		# Get number of records
		self.num_records = query.size()
		if self.num_records == 0:
			self.last_msg = "No s'ha trobat cap registre amb els filtres seleccionats"
			return None

		# Get number of fields
		record = query.record()
		self.num_fields = record.count()
		if self.num_fields == 0:
			self.last_msg = "No s'han especificat camps a retornar"
			return None

		rows = []
		while query.next():
			row = []
			for i in range(self.num_fields):
				row.append(query.value(i))
			rows.append(row)

		return rows

