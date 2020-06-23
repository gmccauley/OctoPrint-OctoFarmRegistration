$(function() {
	function OctoFarmRegistrationViewModel(parameters) {
		var self = this;
		var PLUGIN_ID = 'octofarmregistration'
		
		self.SettingsViewModel = parameters[0];
		//console.log(self.SettingsViewModel);
		
		self.registerInProgress = ko.observable();
		self.restartRequired = ko.observable(true);
		
		self.onDataUpdaterPluginMessage = function(plugin, data) {
			if (plugin != PLUGIN_ID) {
				console.log("Ignoring Plugin: " + plugin);
				return;
			}

			if(data.action == "popup") {
				new PNotify({
					title: 'OctoFarm Registration',
					text: data.text,
					type: data.type,
					hide: true
				});
			}

			if(data.action == "doneRegister") {
				self.SettingsViewModel.settings.plugins.octofarmregistration.OctoFarmID(data.id);
				console.log(self.SettingsViewModel);
				console.log("Registration Complete");
				self.registerInProgress(false);
			}
		}
		
 		self.registerNow = function() {
			console.log("Manual Registration Initiated");
			self.SettingsViewModel.saveData();
			//OctoPrint.settings.savePluginSettings(PLUGIN_ID, {'OctoFarmHost': self.SettingsViewModel.settings.plugins.octofarmregistration.OctoFarmHost(), 'OctoFarmPort': self.SettingsViewModel.settings.plugins.octofarmregistration.OctoFarmPort()});
			
 			self.registerInProgress(true);
			$.ajax({
				url: API_BASEURL + 'plugin/' + PLUGIN_ID,
				type: 'POST',
				datatype: "json",
				data: JSON.stringify({
					command: "Register"
				}),
				contentType: "application/json; charset=UTF-8"
			});			
		};

 		self.restartNow = function() {
			console.log("Showing Restart Prompt");
			showConfirmationDialog({
				message: gettext("<strong>This will restart your OctoPrint server.</strong></p><p>This action may disrupt any ongoing print jobs (depending on your printer's controller and general setup that might also apply to prints run directly from your printer's internal storage)."),
				onproceed: function() {
					OctoPrint.system.executeCommand("core", "restart")
						.done(function() {
							notice.remove();
							new PNotify({
								title: gettext("Restart in progress"),
								text: gettext("The server is now being restarted in the background")
							})
						})
						.fail(function() {
							new PNotify({
								title: gettext("Something went wrong"),
								text: gettext("Trying to restart the server produced an error, please check octoprint.log for details. You'll have to restart manually.")
							})
						});
				}
			});

		};

		self.requestData = function () {
			$.ajax({
				url: API_BASEURL + 'plugin/' + PLUGIN_ID,
				type: "GET",
				dataType: "json"
			});
		};

		self.onBeforeBinding = function() {
			self.settings = self.SettingsViewModel.settings;
			self.restartRequired(self.SettingsViewModel.settings.plugins.octofarmregistration.OctoFarmRestartRequired());
			self.registerInProgress(self.SettingsViewModel.settings.plugins.octofarmregistration.OctoFarmRegistrationInProgress());
		};

		self.onSettingsShown = function() {
			self.requestData();

			if(self.SettingsViewModel.settings.plugins.octofarmregistration.OctoPrintURL() == "") {
				console.log("No OctoPrintURL");
				self.SettingsViewModel.settings.plugins.octofarmregistration.OctoPrintURL(window.location.protocol + "//" + window.location.hostname + ":" + window.location.port)
			}
			
			console.log("OctoPrintURL: " + self.SettingsViewModel.settings.plugins.octofarmregistration.OctoPrintURL());
		};
	}


	OCTOPRINT_VIEWMODELS.push([
		// This is the constructor to call for instantiating the plugin
		OctoFarmRegistrationViewModel,

		// This is a list of dependencies to inject into the plugin, the order which you request
		// here is the order in which the dependencies will be injected into your view model upon
		// instantiation via the parameters argument
		["settingsViewModel"],

		// Finally, this is the list of selectors for all elements we want this view model to be bound to.
		["#settings_plugin_octofarmregistration"]
    ]);
});