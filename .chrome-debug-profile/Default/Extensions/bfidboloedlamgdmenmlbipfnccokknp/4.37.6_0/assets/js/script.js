(function(window) {
  const params = new URLSearchParams(document.currentScript.src.split('?')[1]);
  const latitude = parseFloat(params.get('latitude'));
  const longitude = parseFloat(params.get('longitude'))
  
  navigator.geolocation.getCurrentPosition = (fn) => {
    setTimeout(() => {
      fn({
        coords: {
          accuracy: 10,
          altitude: null,
          altitudeAccuracy: null,
          heading: null,
          latitude: latitude,
          longitude: longitude,
          speed: null,
        },
        timestamp: Date.now(),
      })
    }, 2912)
  };
  navigator.geolocation.watchPosition = (fn) => {
    setTimeout(() => {
      fn({
        coords: {
          accuracy: 10,
          altitude: null,
          altitudeAccuracy: null,
          heading: null,
          latitude: latitude,
          longitude: longitude,
          speed: null,
        },
        timestamp: Date.now(),
      })
    }, 2912)
  };
}(window));

