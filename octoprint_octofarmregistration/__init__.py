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
		if self._settings.get(["OctoFarmRunAtStartup"]):
			if self.StartupCORS:
				self._settings.set(["OctoFarmRestartRequired"], False)
			else:
				self._settings.set(["OctoFarmRestartRequired"], True)
			thread = threading.Timer(0,self.doRegister,["Startup"])
			thread.start()


	def get_settings_defaults(self):
		return dict(OctoPrintURL="",
					OctoFarmHost="",
		            OctoFarmPort="4000",
					OctoFarmSSL=False,
					OctoFarmUser="",
					OctoFarmPass="",
					OctoFarmGroup="",
					OctoFarmID="",
					OctoFarmRestartRequired=False,
					OctoFarmRegistrationInProgress=False,
					OctoFarmRunAtStartup=False,
					OctoFarmRunAtSettingsSave=False)


	def on_settings_save(self, data):
		if "OctoFarmRegistrationInProgress" in data:
			return
		self._logger.debug("Settings Saved")
		self._logger.debug("Settings: " + str(data))
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		if self._settings.get(["OctoFarmRunAtSettingsSave"]):
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
		self._logger.debug("#####  doRegister")
		if self._settings.get(["OctoFarmRegistrationInProgress"]):
			self._logger.info("Registration Already in Progress")
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="notice", text="Registration Already in Progress"))
			return
		self._settings.set(["OctoFarmRegistrationInProgress"], True)
		self._settings.save()
		
		self._logger.info("Starting %s Registration" % type)
		if type == "Startup":
			self._logger.debug("Startup Registration sleeping for 10 seconds to allow OctoPrint to start")
			time.sleep(10)

		# Set CORS
		if self._settings.global_get(["api","allowCrossOrigin"]):
			self._logger.debug("CORS Already Enabled")
		else:   
			self._logger.debug("Enabling CORS")
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
		self._logger.debug("Base URL: " + OctoFarmBaseUrl)
		
		# Login to OctoFarm and get Cookie
		OctoFarmCookie = self.getCookie(OctoFarmBaseUrl)
		self._logger.debug("Cookie: " + str(OctoFarmCookie))
		if OctoFarmCookie is None:
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="doneRegister"))
			self._settings.set(["OctoFarmRegistrationInProgress"], False)
			self._settings.save()
			return

		# Get list of Printers from OctoFarm
		OctoFarmPrinterList = self.getPrinterList(OctoFarmBaseUrl,OctoFarmCookie)
		self._logger.debug("Number of Printers: " + str(len(OctoFarmPrinterList)))
		self._logger.debug("PrinterList: " + str(OctoFarmPrinterList))

		# Get Current OctoPrint Info
		MyInfo = self.getMyInfo()
		self._logger.debug("My Info: " + str(MyInfo))
		
		OctoFarmPrinter = self.isPrinterExists(MyInfo, OctoFarmPrinterList)
		if OctoFarmPrinter is None:
			if self.addPrinter(OctoFarmBaseUrl, OctoFarmCookie, MyInfo):
				self._logger.debug("Registration Succeeded")
				self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="success", text="Registration Succeeded"))
			else:
				self._logger.error("Registration Failed - Unknown Error")
				self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Failed - Unknown Error"))			
		else:
			if self.isPrinterAccurate(MyInfo, OctoFarmPrinter):
				self._logger.info("Printer Already Exists")
				self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="notice", text="Printer Already Exists"))
			else:
				if self.updatePrinter(OctoFarmBaseUrl, OctoFarmCookie, MyInfo):
					self._logger.info("Registration Update Succeeded")
					self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="success", text="Registration Update Succeeded"))
				else:
					self._logger.error("Registration Update Failed - Unknown Error")
					self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Update Failed - Unknown Error"))			

		self._plugin_manager.send_plugin_message(self._identifier, dict(action="doneRegister", id=self._settings.get(["OctoFarmID"])))
		self._settings.set(["OctoFarmRegistrationInProgress"], False)
		self._settings.save()


	def getBaseURL(self):
		self._logger.debug("#####  getBaseURL")
		if self._settings.get(["OctoFarmSSL"]) == True:
			return "https://" + self._settings.get(["OctoFarmHost"]) + ":" + self._settings.get(["OctoFarmPort"])
		else:
			return "http://" + self._settings.get(["OctoFarmHost"]) + ":" + self._settings.get(["OctoFarmPort"])


	def getCookie(self, OctoFarmBaseUrl):
		self._logger.debug("#####  getCookie")
		OctoFarmLoginUrl = OctoFarmBaseUrl + "/users/login"
		LoginData = {'username':self._settings.get(["OctoFarmUser"]),
		             'password':self._settings.get(["OctoFarmPass"])}
		try:
			LoginResponse = requests.post(url = OctoFarmLoginUrl, data = LoginData, allow_redirects=False)
		except requests.exceptions.RequestException as e:
			self._logger.error("Registration Failed - OctoFarm Unavailable")
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Failed - OctoFarm Unavailable"))
			return None
			
		self._logger.debug("getCookie Response Headers: " + str(LoginResponse.headers))
		
		if LoginResponse.headers["Location"] == "/users/login":
			self._logger.error("Registration Failed - Invalid Logon")
			self._plugin_manager.send_plugin_message(self._identifier, dict(action="popup", type="error", text="Registration Failed - Invalid Logon"))
			return None
		else:
			return LoginResponse.cookies.get_dict()


	def getPrinterList(self, OctoFarmBaseUrl, OctoFarmCookie):
		self._logger.debug("#####  getPrinterList")
		OctoFarmUrl = OctoFarmBaseUrl + "/printers/PrinterInfo"
		PrinterInfoResponse = requests.post(url = OctoFarmUrl, cookies = OctoFarmCookie)
		self._logger.debug("getPrinterList Response Headers: " + str(PrinterInfoResponse.headers))
		TruncPrinterList = []
		for Printer in PrinterInfoResponse.json():
			self._logger.debug("###############################   " + str(Printer['settingsAppearance']))
			TruncPrinterList.append({'_id': Printer['_id'], 'printerURL': Printer['printerURL'], 'camURL': Printer['camURL'], 'apikey': Printer['apikey'], 'group': Printer['group'], 'settingsAppearance': Printer['settingsAppearance']})
		return TruncPrinterList


	def getMyInfo(self):
		self._logger.debug("#####  getMyInfo")
		MyInfo = {'_id': '',
				  'apikey': '',
				  'camURL': '',
				  'group': '',
				  'printerURL': ''}
		
		# Get OctoFarm ID
		MyInfo['_id'] = self._settings.get(["OctoFarmID"])
		self._logger.debug("ID: " + str(MyInfo['_id']))

		# Get OctoPrint API Key
		MyInfo['apikey'] = self._settings.global_get(["api","key"])
		if MyInfo['apikey'] is None: MyInfo['apikey'] = ""
		self._logger.debug("apikey: " + MyInfo['apikey'])

		# Get printerURL
		MyInfo['printerURL'] = self._settings.get(["OctoPrintURL"])
		self._logger.debug("printerURL: " + str(MyInfo['printerURL']))

		# Get OctoPrint camURL
		MyInfo['camURL'] = self._settings.global_get(["webcam","stream"])
		if MyInfo['camURL'] is None: MyInfo['camURL'] = ""
		if MyInfo['camURL'] != "": MyInfo['camURL'] = MyInfo['printerURL'] + MyInfo['camURL']
		self._logger.debug("camURL: " + str(MyInfo['camURL']))	

		# Get Group
		MyInfo['group'] = self._settings.get(["OctoFarmGroup"])
		self._logger.debug("group: " + str(MyInfo['group']))

		# Get OctoPrint Settings
		if self._settings.global_get(["appearance","name"]) == "":
			OctoPrintName = self._settings.get(["OctoPrintURL"])
		else:
			OctoPrintName = self._settings.global_get(["appearance","name"])
		MyInfo['settingsAppearance'] = {'color':self._settings.global_get(["appearance","color"]),
                                       'colorTransparent':str(self._settings.global_get(["appearance","colorTransparent"])),
									   'defaultLanguage':self._settings.global_get(["appearance","defaultLanguage"]),
									   'name':OctoPrintName,
									   'showFahrenheitAlso':str(self._settings.global_get(["appearance","showFahrenheitAlso"]))}
		self._logger.debug("printerURL: " + str(MyInfo['settingsAppearance']))
		return MyInfo


	def isPrinterExists(self, MyInfo, OctoFarmPrinterList):
		self._logger.debug("#####  isPrinterExists")
		self._logger.debug("MyInfo['_id']: " + str(MyInfo['_id']))
		bolExists = False
		for OctoFarmPrinter in OctoFarmPrinterList:
			if MyInfo['_id'] == OctoFarmPrinter['_id']:
				self._logger.debug("PrinterExists - _id: " + str(OctoFarmPrinter['_id']))
				return OctoFarmPrinter


	def isPrinterAccurate(self, MyInfo, OctoFarmPrinter):
		self._logger.debug("#####  isPrinterAccurate")
		isAccurate = True
		if MyInfo['apikey'] != OctoFarmPrinter['apikey']:
			self._logger.debug("apikey does not match")
			isAccurate = False
		if MyInfo['camURL'] != OctoFarmPrinter['camURL']:
			self._logger.debug("camURL does not match")
			isAccurate = False
		if MyInfo['group'] != OctoFarmPrinter['group']:
			self._logger.debug("group does not match")
			isAccurate = False
		if MyInfo['printerURL'] != OctoFarmPrinter['printerURL']:
			self._logger.debug("printerURL does not match")
			isAccurate = False
		if MyInfo['settingsAppearance']['color'] != OctoFarmPrinter['settingsAppearance']['color']:
			self._logger.debug("settingsAppearance:color does not match")
			isAccurate = False
		if MyInfo['settingsAppearance']['colorTransparent'] != OctoFarmPrinter['settingsAppearance']['colorTransparent']:
			self._logger.debug("settingsAppearance:colorTransparent does not match")
			isAccurate = False
		if MyInfo['settingsAppearance']['defaultLanguage'] != OctoFarmPrinter['settingsAppearance']['defaultLanguage']:
			self._logger.debug("settingsAppearance:defaultLanguage does not match")
			isAccurate = False
		if MyInfo['settingsAppearance']['name'] != OctoFarmPrinter['settingsAppearance']['name']:
			self._logger.debug("settingsAppearance:name does not match")
			isAccurate = False
		if MyInfo['settingsAppearance']['showFahrenheitAlso'] != OctoFarmPrinter['settingsAppearance']['showFahrenheitAlso']:
			self._logger.debug("settingsAppearance:showFahrenheitAlso does not match")
			isAccurate = False

		return isAccurate


	def addPrinter(self, OctoFarmBaseUrl, OctoFarmCookie, MyInfo):
		self._logger.debug("#####  addPrinter")
		OctoFarmAddUrl = OctoFarmBaseUrl + "/printers/add"
		MyInfo.pop('_id', None)
		self._logger.debug("My Info: " + str([MyInfo]))
		try:
			SaveResponse = requests.post(url = OctoFarmAddUrl, json = [MyInfo], cookies = OctoFarmCookie, timeout=30)
			self._logger.debug("SaveResponse: " + str(SaveResponse))
			self._logger.debug("Response Headers: " + str(SaveResponse.headers))
			self._logger.debug("Status Code: " + str(SaveResponse.status_code))
			self._logger.debug("JSON: " + str(SaveResponse.json()))
			if SaveResponse.status_code == 200:
				self._logger.debug("New ID: " + str(SaveResponse.json()['printersAdded'][0]['_id']))
				self._settings.set(["OctoFarmID"], SaveResponse.json()['printersAdded'][0]['_id'])
				self._settings.save()
				return True
			else:
				return False
		except requests.exceptions.RequestException as e:
			error = e
			self._logger.debug("Error: " + str(e))
			return False


	def updatePrinter(self, OctoFarmBaseUrl, OctoFarmCookie, MyInfo):
		self._logger.debug("#####  updatePrinter")
		OctoFarmAddUrl = OctoFarmBaseUrl + "/printers/update"
		self._logger.debug("My Info: " + str([MyInfo]))
		try:
			SaveResponse = requests.post(url = OctoFarmAddUrl, json = [MyInfo], cookies = OctoFarmCookie, timeout=30)
			self._logger.debug("SaveResponse: " + str(SaveResponse))
			self._logger.debug("Response Headers: " + str(SaveResponse.headers))
			self._logger.debug("Status Code: " + str(SaveResponse.status_code))
			self._logger.debug("JSON: " + str(SaveResponse.json()))
			if SaveResponse.status_code == 200:
				return True
			else:
				return False
		except requests.exceptions.RequestException as e:
			error = e
			self._logger.debug("Error: " + str(e))
			return False





__plugin_name__ = "OctoFarm Registration"
__plugin_pythoncompat__ = ">=2.7,<4"
__plugin_implementation__ = OctoFarmRegistrationPlugin()