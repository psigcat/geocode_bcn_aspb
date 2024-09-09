import os

from PyQt5.QtSql import QSqlDatabase, QSqlQuery


class GisAspbDB:

	def __init__(self, plugin_dir, config_file="GisAspb.conf"):

		self.plugin_dir = plugin_dir
		self.config_file = config_file
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

		filepath = os.path.join(self.plugin_dir, self.config_file)
		if not os.path.exists(filepath):
			return
		file = open(filepath, "r")
		if file.closed:
			return

		params = ["host", "database", "port", "user", "password", "service", "schema"]
		for i in params:
			self.param[i] = ""
		for reg in file:
			if reg.startswith("host="):
				self.param["host"] = str(reg.split("host=")[1]).strip()
			if reg.startswith("database="):
				self.param["database"] = str(reg.split("database=")[1]).strip()
			if reg.startswith("port="):
				self.param["port"] = str(reg.split("port=")[1]).strip()
			if reg.startswith("user="):
				self.param["user"] = str(reg.split("user=")[1]).strip()
			if reg.startswith("password="):
				self.param["password"] = str(reg.split("password=")[1]).strip()
			if reg.startswith("service="):
				self.param["service"] = str(reg.split("service=")[1]).strip()
			if reg.startswith("schema="):
				self.param["schema"] = str(reg.split("schema=")[1]).strip()
				self.param["search_path"] = self.param["schema"]
		file.close()


	def ObrirBaseDades(self):
		""" Obrir base de dades servidor """

		if self.bd_open:
			return self.db

		if self.param["host"] == "" and self.param["service"] == "":
			self.last_error = "No s'ha definit ni host ni service"
			return None

		self.db = QSqlDatabase.addDatabase("QPSQL", "gis_aspb")
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

