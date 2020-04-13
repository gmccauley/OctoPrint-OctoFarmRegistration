$(function() {
	function OctoFarmRegistrationViewModel(parameters) {
		var self = this;
		self.settingsViewModel = parameters[0];
		
		self.onDataUpdaterPluginMessage = function(plugin, data) {
			if (plugin != "octofarmregistration") {
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
		}
	}
	
	$("#RegisterNow").click(function () {
		$.ajax({
			url: API_BASEURL + 'plugin/octofarmregistration',
			type: 'POST',
			datatype: "json",
			data: JSON.stringify({
				command: "Register"
			}),
			contentType: "application/json; charset=UTF-8"
		});
	});

	OCTOPRINT_VIEWMODELS.push([
		// This is the constructor to call for instantiating the plugin
		OctoFarmRegistrationViewModel,

		// This is a list of dependencies to inject into the plugin, the order which you request
		// here is the order in which the dependencies will be injected into your view model upon
		// instantiation via the parameters argument
		["settingsViewModel"]

		// Finally, this is the list of selectors for all elements we want this view model to be bound to.
		//["#tab_plugin_helloworld"]
    ]);
});