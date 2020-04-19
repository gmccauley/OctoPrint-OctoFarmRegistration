# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import octoprint.plugin
import requests
import socket
import threading
import time

class OctoFarmRegistrationPlugin(octoprint.plugin.StartupPlugin,
                       octoprint.plugin.TemplatePlugin,
					   octoprint.plugin.SettingsPlugin,
					   octoprint.plugin.AssetPlugin,
					   octoprint.plugin.SimpleApiPlugin):

	def on_startup(self, host, port):
		self.StartupPort = port
		self.StartupCORS = self._settings.global_get(["api","allowCrossOrigin"])


	def on_after_startup(self):
		self._settings.set(["OctoFarmRegistrationInProgress"], False)
		if self.StartupCORS:
			self._settings.set(["OctoFarmRestartRequired"], False)
		else:
			self._settings.set(["OctoFarmRestartRequired"], True)
		thread = threading.Timer(0,self.doRegister,["Startup"])
		thread.start()


	def get_settings_defaults(self):
		return dict(OctoFarmHost="",
		            OctoFarmPort="4000",
					OctoFarmSSL=False,
					OctoFarmUser="",
					OctoFarmPass="",
					OctoFarmRestartRequired=False,
					OctoFarmRegistrationInProgress=False)


	def on_settings_save(self, data):
		if "OctoFarmRegistrationInProgress" in data:
			return
		self._logger.info("Settings Saved")
		self._logger.info("Settings: " + str(data))
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		thread = threading.Timer(0,self.doRegister,["Manual"])
		thread.start()


	def get_assets(self):
		return dict(
			js=["js/octofarmregistration.js"]
		)


	def is_api_adminonly(self):    
		return True 


	def get_api_commands(self):
		return dict(
			Register=[]
		)


	def on_api_command(self, command, data):
		import flask
		if command == "Register":
			if not self._settings.get(["OctoFarmRegistrationInProgress"]):
				thread = threading.Timer(0,self.doRegister,["Manual"])
				thread.start()


	def doRegister(self, type):
		if self._settings.get(["OctoFarmRegistrationInProgress"]):
			self._logger.info("Registration Already in Progress")
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="notice", text="Registration Already in Progress"))
			return
		self._settings.set(["OctoFarmRegistrationInProgress"], True)
		self._settings.save()
		
		self._logger.info("Starting %s Registration" % type)
		if type == "Startup":
			self._logger.info("Startup Registration sleeping for 10 seconds to allow OctoPrint to start")
			time.sleep(20)
		else:
			time.sleep(10)

		# Set CORS
		if self._settings.global_get(["api","allowCrossOrigin"]):
			self._logger.info("CORS Already Enabled")
		else:   
			self._logger.info("Enabling CORS")
			self._settings.global_set(["api","allowCrossOrigin"], True)
			self._settings.save()
			if type == "Startup":
				self._logger.info("Restart Required to enable CORS")
				self._settings.set(["OctoFarmRegistrationInProgress"], False)
				self._settings.save()
				return
		
		# Check For Settings
		bolError = False
		if self._settings.get(["OctoFarmHost"]) == "":
			self._logger.warn("No OctoFarm Hostname")
			bolError = True
		if self._settings.get(["OctoFarmPort"]) == "":
			self._logger.warn("No OctoFarm Port Number")
			bolError = True
		if self._settings.get(["OctoFarmUser"]) == "":
			self._logger.warn("No OctoFarm Username")
			bolError = True
		if self._settings.get(["OctoFarmPass"]) == "":
			self._logger.warn("No OctoFarm Password")
			bolError = True
		if bolError == True:
			self._logger.error("Registration Failed")
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="doneRegister"))
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Failed"))
			self._settings.set(["OctoFarmRegistrationInProgress"], False)
			self._settings.save()
			return
		
		# Build OctoFarm Base URL
		OctoFarmBaseUrl = self.getBaseURL()
		self._logger.info("Base URL: " + OctoFarmBaseUrl)
		
		# Login to OctoFarm and get Cookie
		OctoFarmCookie = self.getCookie(OctoFarmBaseUrl)
		self._logger.info("Cookie: " + str(OctoFarmCookie))
		if OctoFarmCookie is None:
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="doneRegister"))
			self._settings.set(["OctoFarmRegistrationInProgress"], False)
			self._settings.save()
			return

		# Get list of Printers from OctoFarm
		OctoFarmPrinterList = self.getPrinterList(OctoFarmBaseUrl,OctoFarmCookie)
		self._logger.info("Number of Printers: " + str(len(OctoFarmPrinterList)))
		self._logger.info("PrinterList: " + str(OctoFarmPrinterList))

		# Get Current OctoPrint Info
		MyInfo = self.getMyInfo()
		self._logger.info("My Info: " + str(MyInfo))
		
		PrinterIndex = self.isPrinterExists(MyInfo, OctoFarmPrinterList)
		if PrinterIndex is None:
			# Add OctoPrint to Printer List and Save
			MyInfo['index'] = len(OctoFarmPrinterList)
			self._logger.info("My New Info: " + str(MyInfo))
			OctoFarmPrinterList.append(MyInfo)
			self._logger.info("New PrinterList: " + str(OctoFarmPrinterList))
			if self.savePrinters(OctoFarmBaseUrl, OctoFarmCookie, OctoFarmPrinterList):
				self._logger.info("Registration Succeeded")
				self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="success", text="Registration Succeeded"))
			else:
				self._logger.error("Registration Failed - Unknown Error")
				self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Failed - Unknown Error"))			
		else:
			if self.isPrinterAccurate(MyInfo, OctoFarmPrinterList[PrinterIndex]):
				self._logger.info("Printer Already Exists")
				self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="notice", text="Printer Already Exists"))
			else:
				OctoFarmPrinterList[PrinterIndex]['ip'] = MyInfo['ip']
				OctoFarmPrinterList[PrinterIndex]['port'] = MyInfo['port']
				OctoFarmPrinterList[PrinterIndex]['camURL'] = MyInfo['camURL']
				self._logger.info("New PrinterList: " + str(OctoFarmPrinterList))
				if self.savePrinters(OctoFarmBaseUrl, OctoFarmCookie, OctoFarmPrinterList):
					self._logger.info("Registration Update Succeeded")
					self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="success", text="Registration Update Succeeded"))
				else:
					self._logger.error("Registration Update Failed - Unknown Error")
					self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Update Failed - Unknown Error"))			

		self._plugin_manager.send_plugin_message(self._identifier, dict(action="doneRegister"))
		self._settings.set(["OctoFarmRegistrationInProgress"], False)
		self._settings.save()


	def getBaseURL(self):
		if self._settings.get(["OctoFarmSSL"]) == True:
			return "https://" + self._settings.get(["OctoFarmHost"]) + ":" + self._settings.get(["OctoFarmPort"])
		else:
			return "http://" + self._settings.get(["OctoFarmHost"]) + ":" + self._settings.get(["OctoFarmPort"])


	def getCookie(self, OctoFarmBaseUrl):
		OctoFarmLoginUrl = OctoFarmBaseUrl + "/users/login"
		LoginData = {'username':self._settings.get(["OctoFarmUser"]),
		             'password':self._settings.get(["OctoFarmPass"])}
		try:
			LoginResponse = requests.post(url = OctoFarmLoginUrl, data = LoginData, allow_redirects=False)
		except requests.exceptions.RequestException as e:
			self._logger.error("Registration Failed - OctoFarm Unavailable")
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Failed - OctoFarm Unavailable"))
			return None
			
		self._logger.info("getCookie Response Headers: " + str(LoginResponse.headers))
		
		if LoginResponse.headers["Location"] == "/users/login":
			self._logger.error("Registration Failed - Invalid Logon")
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Failed - Invalid Logon"))
			return None
		else:
			return LoginResponse.cookies.get_dict()


	def getPrinterList(self, OctoFarmBaseUrl, OctoFarmCookie):
		OctoFarmUrl = OctoFarmBaseUrl + "/printers/PrinterInfo"
		PrinterInfoResponse = requests.get(url = OctoFarmUrl, cookies = OctoFarmCookie)
		self._logger.info("getPrinterList Response Headers: " + str(PrinterInfoResponse.headers))
		TruncPrinterList = []
		for Printer in PrinterInfoResponse.json():
			TruncPrinterList.append({'index': Printer['index'], 'ip': Printer['ip'], 'port': Printer['port'], 'camURL': Printer['camURL'], 'apikey': Printer['apikey']})
		return TruncPrinterList


	def getMyInfo(self):
		MyInfo = {'index': '',
				  'ip': '',
				  'port': '',
				  'camURL': '',
				  'apikey': ''}
		
		# Get OctoPrint IP
		MyInfo['ip'] = [(s.connect((self._settings.global_get(["server","onlineCheck","host"]), self._settings.global_get(["server","onlineCheck","port"]))), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
		self._logger.info("ip: " + MyInfo['ip'])

		# Get OctoPrint Port
		MyInfo['port'] = str(self.StartupPort)
		self._logger.info("port: " + MyInfo['port'])

		# Get OctoPrint camURL
		MyInfo['camURL'] = self._settings.global_get(["webcam","stream"])
		if MyInfo['camURL'] is None: MyInfo['camURL'] = ""
		if MyInfo['camURL'] != "": MyInfo['camURL'] = MyInfo['ip'] + MyInfo['camURL']
		self._logger.info("camURL: " + str(MyInfo['camURL']))	

		# Get OctoPrint API KeyError
		MyInfo['apikey'] = self._settings.global_get(["api","key"])
		if MyInfo['apikey'] is None: MyInfo['apikey'] = ""
		self._logger.info("apikey: " + MyInfo['apikey'])

		return MyInfo


	def isPrinterExists(self, MyInfo, OctoFarmPrinterList):
		for OctoFarmPrinter in OctoFarmPrinterList:
			if MyInfo['apikey'] == OctoFarmPrinter['apikey']:
				self._logger.info("isPrinterExists: " + str(OctoFarmPrinter['index']))
				return OctoFarmPrinter['index']


	def isPrinterAccurate(self, MyInfo, OctoFarmPrinter):
		if MyInfo['ip'] == OctoFarmPrinter['ip'] and str(MyInfo['port']) == str(OctoFarmPrinter['port']) and MyInfo['camURL'] == OctoFarmPrinter['camURL']:
			return True
		else:
			return False


	def savePrinters(self, OctoFarmBaseUrl, OctoFarmCookie, OctoFarmPrinterList):
		OctoFarmSaveUrl = OctoFarmBaseUrl + "/printers/save"
		OctoFarmInitUrl = OctoFarmBaseUrl + "/printers/runner/init"
		try:
			SaveResponse = requests.post(url = OctoFarmSaveUrl, json = OctoFarmPrinterList, cookies = OctoFarmCookie, timeout=30)
			self._logger.info("SaveResponse: " + str(SaveResponse))
		except requests.exceptions.RequestException as e:
			error = e
			self._logger.info("Error: " + str(e))
		#self._logger.info("savePrinters Response Headers: " + str(SaveResponse.headers))
		#self._logger.info("savePrinters Status Code: " + str(SaveResponse.status_code))
		if SaveResponse.status_code == 200:
			InitResponse = requests.post(url = OctoFarmInitUrl, cookies = OctoFarmCookie, timeout=30)
			self._logger.info("InitResponse: " + str(InitResponse))
			return True
		else:
			return False


	def saveSettings(self):
		self._logger.info(self._settings.get(["OctoFarmHost"]))


__plugin_name__ = "OctoFarm Registration"
__plugin_pythoncompat__ = ">=2.7,<4"
__plugin_implementation__ = OctoFarmRegistrationPlugin()