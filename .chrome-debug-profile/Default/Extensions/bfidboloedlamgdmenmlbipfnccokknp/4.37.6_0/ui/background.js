try {
  importScripts(
    "../bower_components/crypto-js/crypto-js.js",
    "../bower_components/crypto-js/aes.js",
    "../bower_components/crypto-js/md5.js",
    "../bower_components/crypto-js/enc-base64.js",
    "../bower_components/simple-uuid/uuid.js",
    "../config/constant.js",
    "../config/config.js",
    "../library/common.js",
    "../library/storage.js",
    "../library/tabs.js",
    "../library/auth.js",
    "../library/proxy.js",
    "../library/uri.js",
    "../library/messenger.js",
    "../library/pure.js",
    "../library/popup_campaign.js",
    "../library/banner_campaign.js"
  );
} catch (error) {
  console.log("error: ", error);
}
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.redirect) {
      if (sender.tab && sender.tab.id) {
          chrome.tabs.update(sender.tab.id, {url: request.redirect});
      } else {
          chrome.tabs.create({url: request.redirect});
      }
      sendResponse({status: "redirected"});
  }
});

