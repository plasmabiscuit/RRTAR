(function(window) {
  chrome.storage.local.get(["latitude", "longitude", "locationSpoofing"],
    function(storage) {
      if (storage.locationSpoofing &&
        storage.latitude && storage.longitude
      ) {
        var script = document.createElement("script");
        script.src = chrome.runtime.getURL('assets/js/script.js?') + new URLSearchParams({longitude: storage.longitude, latitude: storage.latitude});
        //document.documentElement.prepend(script);
        script.onload = function() {
            this.remove();
        };
        (document.head || document.documentElement).appendChild(script);
      }
    });
}(window));