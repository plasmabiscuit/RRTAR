/*
*	PureVPN
*	by GZ systems Ltd.
*	Everyone is permitted to copy and distribute verbatim copies
*	of this document, but changing it is not allowed.
*
*	This program is distributed in the hope that it will be useful,
*	but WITHOUT ANY WARRANTY; without even the implied warranty of
*	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
*
*	copyright 2016 All Rights are Reserved.
*/

(function() {
  'use strict';
  var onPortMessage = function(oPort) {
    if (oPort.name === "offlineStatus") {
      oPort.onMessage.addListener(function(oRequest) {
        // console.log(oRequest);
        if (oRequest.isOnline === true) {
          $(".connectionError").addClass("hide");
        } else {
          $(".connectionError").removeClass("hide");
        }
      });
    }
  };
  chrome.runtime.onConnect.addListener(onPortMessage);
})();
