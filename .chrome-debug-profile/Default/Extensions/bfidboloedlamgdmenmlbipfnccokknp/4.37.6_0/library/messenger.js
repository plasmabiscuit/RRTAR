/*
*   PureVPN
*   by GZ systems Ltd.
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
  pVn.SocialProviderWindowID = -1;
  pVn.SocialProviderResponse = {};
  pVn.socialResponseCallback = pVn.nofunc;
  var onMessage = function(oRequest, oSender, callback) {
    switch (oRequest.what) {
      // Sync
      case "getAutoLoginCode":
        pVn.auth.getAutoLoginCode(function(response) {
            callback(response);
        });
        return true;
      case "getVpnPassword":
        pVn.auth.setPostAuthentication(oRequest.data.username, callback)
        return true;
      case "initiateOauth":
        pVn.auth.initiateOauth(oRequest.data, callback)
        return true;
      case "popupData":
        pVn.getPopupData(oRequest.tabId, callback);
        return true;
      case "authUser":
        pVn.auth.refreshAccessToken(callback);
        return true;
      case "logOut":
        pVn.auth.del(oRequest.tabId, oRequest.removeAccounts, callback);
        return true;
      case "regionList":
        pVn.proxy.getCountries(callback);
        return true;
      case "toggleProxyService":
        pVn.proxy.proxyService(oRequest.countryCode, callback);
        return true;
      case "updateSettings":
        pVn.proxy.proxyPreference(oRequest.preference,
          oRequest.region, oRequest.domain, callback);
        return true;
      case "editFavourite":
        pVn.proxy.editFavourite(oRequest.countryCode,
          oRequest.status, callback);
        return true;
      case "editFavouriteChannel":
        pVn.proxy.editFavouriteChannel(oRequest.channelCode,
          oRequest.status, callback);
        return true;
      case "editFavouriteCity":
        pVn.proxy.editFavouriteCity(oRequest.cityCode,
          oRequest.isoCode, oRequest.status, callback);
        return true;
      case "editWebRTC":
        pVn.setWebRTC(oRequest.status, callback);
        return true;
      case "toggleWebRtc":
        pVn.toggleWebRtc(oRequest.status, callback);
        return true;
      case "restoreDefaultState":
        pVn.masterReset(callback);
        return true;
      case "defaultCountry":
        pVn.proxy.setCountryCode(oRequest.countryCode,
          oRequest.serverKey,
          oRequest.cityHostname, oRequest.serverName, callback);
        return true;
      case "getUserStatus":
        pVn.userStatus(callback);
        return true;
      case "Feedback_MakeUsHappyCTA":
        pVn.makeUsHappy(callback);
        return true;
      case "userSignup":
        return true;
      case "verifyUser":
        return true;
      case "resendVerification":
        return true;
      case "getSocial":
        return true;
      case "subscriptionStatus":
        pVn.getSubscriptionsDetails(callback);
        return true;
      case "editProxyAutoConnect":
        pVn.setProxyAutoConnect(oRequest.status, callback);
        return true;
      case "updateDesireOutcome":
        pVn.updateDesireOutcome(oRequest.status, oRequest.options, callback);
        return true;
      case "updateCurrentSession":
        pVn.updateCurrentSession(oRequest.connectionStatus, callback);
        return true;
      case "disconnectSessionRatingCheck":
        pVn.disconnectSessionRatingCheck(callback);
        return true;
      case "updateSessionRating":
        pVn.updateSessionRating(oRequest.status, oRequest.options, callback);
        return true;
      case "updateSessionRatingMessageUserInteraction":
        pVn.updateSessionRatingMessageUserInteraction(
          oRequest.status, callback);
        return true;
      case "submitFeedbackFormResult":
        pVn.submitFeedbackFormResult(oRequest.data, callback);
        return true;
      case "updateStoreRatePopup":
        pVn.updateStoreRatePopup(oRequest.value, callback);
        return true;
      case "talkToSupportPopup":
        pVn.talkToSupportPopup(oRequest.value, callback);
        return true;
      case "updateReferAFriendPopup":
        pVn.updateReferAFriendPopup(oRequest.value, oRequest.link, callback);
        return true;
      case "feedbackSkipButton":
        pVn.feedbackSkipButton(callback);
        return true;
        // ASync
      case "openLink":
        pVn.tabs.openLink(oRequest.url);
        break;
      case "clientUserName":
        pVn.clientUserName = oRequest.clientUserName;
        break;
      case "clientSignupDetail":
        pVn.clientSignupDetail.email = oRequest.email;
        pVn.clientSignupDetail.consent = oRequest.consent;
        break;
      case "openApplicationPage":
        pVn.openApplicationPage(oRequest.appname);
        break;
      case "feedBack":
        pVn.proxyPanelNotifications('ProxyExtension_CTA_FeedBack');
        break;
      case "subscribeStatus":
        pVn.proxyPanelNotifications('ProxyExtension_CTA_Purchase', {
          purchaseMessage: oRequest.subscribeMsg,
          buttonText: oRequest.upgradeText
        });
        break;
      case "showFeedbackPage":
        pVn.feedbackRatings();
        break;
      case "ProxyExtension_Feedback":
        pVn.feedbackSubmit(oRequest.submitData);
        break;
      case "socialSignupResult":
        // console.log("socialSignupResult:%o", oRequest);
        pVn.SocialProviderResponse = oRequest.oResponse;
        chrome.tabs.remove(oSender.tab.id);
        break;
      case "openUpgradeAccount":
        pVn.proxy.requestUpgradeUrl(oRequest.upgradeFrom);
        pVn.proxyPanelNotifications('ProxyExtension_CTA_Purchase', {
          purchaseMessage: 'Premium_Upgrade',
          buttonText: oRequest.upgradeText
        });
        break;
      case "campaignPopUp":
        pVn.popupCampaign.popupStatus(oRequest.status);
        break;
      case "campaignBanner":
        pVn.bannerCampaign.bannerStatus(oRequest.status);
        break;
      case "showSignupScreen":
        pVn.showSignupScreen = true;
        break;
      case "updateWhitelistedHosts":
        pVn.updateWhitelistedHosts(oRequest, callback);
        return true;
      case "updateAllowWhitelistedHosts":
        pVn.updateAllowWhitelistedHosts(oRequest.allowWhitelistedHosts,
          callback);
        return true;
      case "editLocationSpoofing":
        pVn.setLocationSpoofing(oRequest.status, callback);
        pVn.proxyPanelNotifications('ProxyExtension_HideGpsLocation', {
          gps_status: oRequest.status
        });
        return true;
      case "toggleLocationSpoofing":
        pVn.toggleLocationSpoofing(oRequest.status, callback);
        return true;
      case "getWhitelistedHostsDetails":
        pVn.getWhitelistedHostsDetails(callback);
        return true;
      case "getClientRedirectToken":
        pVn.auth.userMemberAreaRedirectToken(oRequest.slug, callback);
        return true;
      case "getBannerStatus":
        pVn.bannerCampaign.getBannerStatus(callback);
        return true;
      case "migrateUser":
        pVn.proxy.redirectToMigration(callback);
        return true;
      case "getVpnusernames":
        pVn.getVpnusername(callback);
        return true;
      case "clearUserAccounts":
        pVn.clearUserAccounts();
        return true;
      case "getServers":
        pVn.proxy.getServers(oRequest.city_id, oRequest.type,
          callback);
        return true;
      case "unableToFindServerEvent":
        pVn.proxyPanelNotifications('ProxyExtension_UnableToFindServer', {
          serverHostname: oRequest.serverHostname
        });
        break;
      case "openMemberUrl":
        pVn.proxy.openMemberUrl(oRequest.slug);
        break;
      case "getReferFriend":
        pVn.proxy.getReferFriend(callback);
        return true;
      case "referFriendClickedEvent":
        pVn.proxyPanelNotifications('ProxyExtension_ReferFriendPageClicked',
          {});
        break;
      case "referFriendInviteClickedEvent":
        pVn.proxyPanelNotifications('ProxyExtension_ReferFriendInviteClicked',
          {});
        break;
      case "sendLocationRequest":
        pVn.proxyPanelNotifications('ProxyExtension_LocationRequest', {
          comment: oRequest.comment,
          type: oRequest.type
        });
        break;
      case "referFriendInviteFailedEvent":
        pVn.proxyPanelNotifications('ProxyExtension_ReferInviteFail',
          {});
        break;
      case "connectedEvent":
        var params = {
          session_type: oRequest.sessionType,
          prompt_type: oRequest.promptType,
          connectVia: oRequest.connectVia,
          hostName: "",
          countryName: "",
          cityName: "",
          channelName: ""
        };
        if (oRequest.connectVia === "Host") {
          params.hostName = oRequest.hostName;
          params.type = 'Dedicated Server';
          params.location_code = oRequest.countryName;
          params.location_name = `${oRequest.countryName}_${pVn.systemSettings.dedicated_server.city_iso}`;
          params.client_type = oRequest.client_type;
        }else if (oRequest.connectVia === "teamHost") {
          params.hostName = oRequest.hostName;
          params.type = 'Team Server';
          params.location_code = oRequest.countryName;
          params.location_name = `${oRequest.countryName}_${pVn.systemSettings.team_server.city_iso}`;
          params.client_type = oRequest.client_type;
        } else if (oRequest.connectVia === "Country") {
          params.countryName = oRequest.countryName;
        } else if (oRequest.connectVia === "City" ||
          oRequest.connectVia === "Server") {
          params.cityName = pVn.getCityNameByCityCode(oRequest.countryName, pVn.systemSettings.cities);
        } else if (oRequest.connectVia === "Channel") {
          params.channelName = oRequest.countryName;
        }
        pVn.proxyPanelNotifications(params.hostName ? 'ProxyExtension_Connect' : 'ProxyExtension_ViewSessionPrompt', params);
        break;
      case "ratingOrDOFeedbackEvent":
        var countryCode = pVn.systemSettings.site_prefs["*"];
        if (countryCode === undefined) {
          countryCode = oRequest.countryCode;
        }
        pVn.proxyPanelNotifications('ProxyExtension_RateSessionPrompt', {
          session_type: oRequest.sessionType,
          prompt_type: oRequest.promptType,
          rating: oRequest.rating,
          proxy_host: pVn.proxyNodes[countryCode]?.proxy_host,
        }, callback);
        return true;
      case "sessionFeedbackReasonsEvent":
        var countryCode = pVn.systemSettings.site_prefs["*"];
        if (countryCode === undefined) {
          countryCode = oRequest.countryCode;
        }

          var props1 = {
            session_type: oRequest.sessionType,
            prompt_type: oRequest.promptType,
            connectVia: oRequest.connectVia,
            rating: oRequest.rating,
            comment: oRequest.comment,
            proxy_host: pVn.proxyNodes[countryCode]?.proxy_host || pVn.systemSettings.lastHostName, // If extension refreshed -> it takes the Last Host Name.
            reason: oRequest.reason,
            submit: oRequest.submit,
            email: oRequest.userEmail,
            user_full_name: oRequest.userFullName,
            countryName: "",
            cityName: "",
            channelName: ""
          };



          if (oRequest.connectVia === "Country") {
            props1.countryName = oRequest.countryName;
          } else if (oRequest.connectVia === "City" ||
            oRequest.connectVia === "Server") {
            props1.cityName = pVn.getCityNameByCityCode(oRequest.countryName, pVn.systemSettings.cities);
          } else if (oRequest.connectVia === "Channel") {
            props1.channelName = oRequest.countryName;
          }
        pVn.proxyPanelNotifications('ProxyExtension_SessionFeedback', props1);
        break;
      case "storeRatePopupEvent":
        pVn.proxyPanelNotifications('ProxyExtension_StoreFeedback', {
          action: oRequest.action,
          prompt_type: oRequest.promptType
        });
        break;
      case "liveChatPopupEvent":
        pVn.proxyPanelNotifications('ProxyExtension_ViewLiveChatPopup', {
          action: oRequest.action
        });
        break;
      case "referredAFriendPopupAppearsEvent":
        pVn.proxyPanelNotifications('ProxyExtension_ViewReferAFriend', {
          session_type: oRequest.sessionType,
          prompt_type: oRequest.promptType
        });
        break;
      case "referredAFriendPopupClickEvent":
        var props2 = {
          connectVia: oRequest.connectVia,
          prompt_type: oRequest.promptType,
          countryName: "",
          cityName: "",
          channelName: ""
        };
        

        if (oRequest.connectVia === "Country") {
          props2.countryName = oRequest.countryName;
        } else if (oRequest.connectVia === "City" ||
          oRequest.connectVia === "Server") {
          props2.cityName = pVn.getCityNameByCityCode(oRequest.countryName, pVn.systemSettings.cities);
        } else if (oRequest.connectVia === "Channel") {
          props2.channelName = oRequest.countryName;
        }
        pVn.proxyPanelNotifications('ProxyExtension_ClickReferAFriend', props2);
        break;
      // skip default case
    }
    return true;
  };

  //! Social signup
  var initSocialSignup = function(oRequest, callback) {
    if (!callback || typeof callback !== "function") {
      callback = pVn.nofunc;
    }
    var onInit = function(oWindow) {
      pVn.SocialProviderWindowID = oWindow.id;
    };
    chrome.windows.create({
      url: oRequest.url,
      type: "popup",
      focused: true
    }, onInit);
  };

  var onPortMessage = function(oPort) {
    //! Post the message to popup
    var postMessage = function(oResponse) {
      if (chrome.extension.getViews({type: "popup"}).length > 0) {
        try {
          oPort.postMessage(oResponse);
        } catch (e) {
          // console.log("catch error: oResponse:%o, e:%o", oResponse, e);
        }
      }
    };
    //! Social Signup port message
    var onSocialSignupMessage = function(oRequest) {
      if (oRequest.open) {
        pVn.isReady = false;
        pVn.showSignupScreen = true;
        pVn.showSignUpLoader = true;
        initSocialSignup(oRequest, postMessage);
      }
    };
    //! Login port message
    /* var onLoginMessage = function(oRequest) {
      if (oRequest.open) {
        pVn.auth.set(oRequest.data, postMessage);
      }
    };*/

    switch (oPort.name) {
      case "socialSignup":
        oPort.onMessage.addListener(onSocialSignupMessage);
        pVn.socialResponseCallback = postMessage;
        break;
      case "authUser":
        // oPort.onMessage.addListener(onLoginMessage);
        break;
        // skip default case
    }
  };

  chrome.runtime.onMessage.addListener(onMessage);

  var options = { mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7 };

  var getDecryptedPassword = function (encJson, salt) {
      var encryptedJson = typeof encJson === "string" ? JSON.parse(encJson) : encJson;
      var decrypted = CryptoJS.AES.decrypt(encryptedJson, salt, options);
      return decrypted.toString(CryptoJS.enc.Utf8);
  };

  // Global variable to store credentials
  var cachedCredentials = {
    username: '',
    password: '',
    encJson: '',
    salt: ''
  };

    // Function to get credentials from chrome.storage.local using Promises
  async function getCredentialsFromStorage() {
    return new Promise((resolve, reject) => {
      chrome.storage.local.get(['user_name', 'encJson', 'salt'], function(result) {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve(result);
        }
      });
    });
  }

  // Function to ensure credentials are available (either in cache or storage)
  async function ensureCredentials() {
    if (!cachedCredentials.username || !cachedCredentials.password) {
      try {
        const result = await getCredentialsFromStorage();
        if (result.user_name && result.encJson && result.salt) {
          cachedCredentials.username = String(result.user_name);
          cachedCredentials.encJson = result.encJson;
          cachedCredentials.salt = result.salt;
          var password = getDecryptedPassword(result.encJson, result.salt);
          cachedCredentials.password = String(password);
        }
      } catch (error) {
        console.error("Error loading credentials:", error);
      }
    }
  }

  // Handle the `onAuthRequired` event to provide credentials automatically
  chrome.webRequest.onAuthRequired.addListener(
    async function(details, callbackFn) {
      // Ensure credentials are available, either from memory or storage
      await ensureCredentials();

      if (cachedCredentials.username && cachedCredentials.password) {
        callbackFn({
          authCredentials: {
            username: cachedCredentials.username,
            password: cachedCredentials.password
          }
        });
      } else {
        callbackFn(); // Proceed without credentials if none are available
      }
    },
    { urls: ["<all_urls>"] }, // Replace with your specific proxy URLs if needed
    ['asyncBlocking']
  );

  // If credentials are updated, update the global cache
  chrome.storage.onChanged.addListener((changes) => {
    let shouldUpdatePassword = false;

    // Check if user_name has changed
    if (changes.user_name) {
      cachedCredentials.username = String(changes.user_name.newValue) || cachedCredentials.username;
      shouldUpdatePassword = true;
    }

    // Check if encJson has changed
    if (changes.encJson) {
      cachedCredentials.encJson = String(changes.encJson.newValue) || cachedCredentials.encJson;
      shouldUpdatePassword = true;
    }

    // Check if salt has changed
    if (changes.salt) {
      cachedCredentials.salt = String(changes.salt.newValue) || cachedCredentials.salt;
      shouldUpdatePassword = true;
    }

    // Only update password if encJson and salt are available and relevant fields changed
    if (shouldUpdatePassword && cachedCredentials.salt && cachedCredentials.encJson) {
      cachedCredentials.password = getDecryptedPassword(cachedCredentials.encJson, cachedCredentials.salt);
    }
  });

  // Call this function to refresh the credentials at startup
  chrome.runtime.onStartup.addListener( async () => {
    await ensureCredentials();
    startHeartbeat();
  });

  chrome.runtime.onSuspend.addListener(() => {
    stopHeartbeat();
  });

  chrome.runtime.onInstalled.addListener(() => {
    startHeartbeat();
  });

  let heartbeatInterval;

  async function runHeartbeat() {
    await chrome.storage.local.set({ 'last-heartbeat': new Date().getTime() });
  }

  /**
   * Starts the heartbeat interval which keeps the service worker alive. Call
   * this sparingly when you are doing work which requires persistence, and call
   * stopHeartbeat once that work is complete.
   */
  async function startHeartbeat() {
    // Run the heartbeat once at service worker startup.
    runHeartbeat().then(() => {
      // Then again every 20 seconds.
      heartbeatInterval = setInterval(runHeartbeat, 20 * 1000);
    });
  }

  async function stopHeartbeat() {
    clearInterval(heartbeatInterval);
  }

  /**
   * Returns the last heartbeat stored in extension storage, or undefined if
   * the heartbeat has never run before.
   */
  async function getLastHeartbeat() {
    return (await chrome.storage.local.get('last-heartbeat'))['last-heartbeat'];
  }


  chrome.proxy.settings.onChange.addListener(pVn.proxy.onControlChange);
  chrome.management.onEnabled.addListener(function(oExtensionInfo) {
    // console.log("oExtensionInfo :%s",oExtensionInfo);
    pVn.getExtensionDetails(oExtensionInfo, false);
  });
  chrome.management.onDisabled.addListener(function(oExtensionInfo) {
    // console.log("oExtensionInfo :%s",oExtensionInfo);
    pVn.getExtensionDetails(oExtensionInfo, true);
  });
  chrome.tabs.onRemoved.addListener(function(iTabId) {
    // ! confirm closed tab id is created by rating feedback
    if (iTabId === pVn.tabId) {
      pVn.systemSettings.feedbackData.currentDate = pVn.makeDate();
      pVn.systemSettings.feedbackData.updateDate = pVn.makeDate(3650);
      pVn.systemSettings.feedBackStatus = pVn.checkFeedBackStatus = false;
      //! Update storage
      pVn.storage.set({
        feedbackData: pVn.systemSettings.feedbackData,
        feedBackStatus: pVn.checkFeedBackStatus
      });
    }
  });
  //! Update tab details
  chrome.tabs.onCreated.addListener(pVn.tabs.add);
  chrome.tabs.onRemoved.addListener(pVn.tabs.del);
  chrome.tabs.onUpdated.addListener(pVn.tabs.update);
  chrome.webNavigation.onBeforeNavigate.addListener(pVn.tabs.edit);
  chrome.runtime.onConnect.addListener(onPortMessage);
  chrome.windows.onRemoved.addListener(function(iWindowID) {
    // ! unset proxy when window closes
    chrome.windows.getAll(function(windows) {
      if (windows.length <= 0) {
        // ! set proxy session time when user still connected
        if (pVn.isEmpty(pVn.systemSettings.site_prefs) === false) {
          pVn.systemSettings.session_time = new Date().toMysqlFormat();
          // ! make sure we have got the session id
          if (pVn.systemSettings.session_id) {
            pVn.storage.set({
              session_id: pVn.systemSettings.session_id,
              session_time: pVn.systemSettings.session_time
            }, chrome.proxy.settings.clear);
          }
        }
      }
    });

    if (iWindowID === pVn.SocialProviderWindowID) {
      var responseMessage = '';
      if (pVn.SocialProviderResponse &&
          pVn.isEmpty(pVn.SocialProviderResponse) === false) {
        if (pVn.SocialProviderResponse.hasOwnProperty("token") === true) {
          setTimeout(function() {
            pVn.auth.socialLoginAuthentication(pVn.SocialProviderResponse,
              pVn.socialResponseCallback);
          }, 2000);
          return;
        }
        responseMessage = pVn.SocialProviderResponse.error_description;
      } else {
        responseMessage = "WINDOW_CLOSED";
        pVn.showSignUpLoader = false;
      }
      setTimeout(function() {
        pVn.socialResponseCallback({
          close: true,
          error: responseMessage
        });
      }, 2000);
    }
  });
  /*chrome.windows.onCreated.addListener(function() {
    pVn.systemSettings.use_cloudfront_domain = false;
  });*/ 

  // since in MV3, we can not set interval to fire the
  // refresh token callback, so adding alarm so it
  // does the refresh once it invoked
  chrome.alarms.onAlarm.addListener(function(alarm){
    switch (alarm.name) {
    case "silentAccessTokenRefresh":
      pVn.auth.refreshAccessToken();
      break;
    case "proxyUnblockAlarm":
      //console.log("alarm");      
      break;
    case "switchServices":
      pVn.switchServices();
    }
  });

  /* chrome.sessions.onChanged.addListener(function() {
    setTimeout(function() {
    chrome.runtime.reload();
    }, 1000);
  });*/
})();
