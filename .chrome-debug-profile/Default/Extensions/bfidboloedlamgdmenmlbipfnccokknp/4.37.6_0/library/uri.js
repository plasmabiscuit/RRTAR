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
  pVn.uri = (function() {
    var uriInterval;
    //! return url or protocol when non http/https url.
    var removeUrlProtocol = function(sUrl) {
      return sUrl.replace(RE_PROTO, '');
    };
    var get = function(sUrl, bStrict) {
      sUrl = sUrl.trim();
      var protocol = RE_PROTOCOL.exec(sUrl);
      if (protocol === null) {
        return sUrl;
      }

      if (protocol[0].startsWith("http")) {
        return sUrl;
      }
      if (!bStrict) {
        return protocol[0];
      }
      return sUrl;
    };

    //! extract host from url
    var getHost = function(sUrl, bNowww) {
      var sHost;
      if (sUrl === "" || sUrl === false || typeof sUrl === "undefined") {
        return false;
      }
      sUrl = sUrl.trim();
      // Check for system schemes
      if (new RegExp("^(" + pVn.systemSchemes.join("|") + ")").test(sUrl)) {
        // return pVn.browserScheme;
        return sUrl;
      }
      // find & remove protocol (http, ftp, etc.) and get host
      if (sUrl.indexOf("://") > -1) {
        sHost = sUrl.split('/')[2];
      } else {
        sHost = sUrl.split('/')[0];
      }

      sHost = sHost.split(':')[0];
      if (bNowww) {
        sHost = removeUrlProtocol(sHost);
      }

      return sHost;
    };

    var getDomain = function(sUrl) {
      return getHost(sUrl, true);
    };

    var domainMatch = function(sDomainA, sDomainB) {
      //! match host tail and either match length or backward char if it a . (dot)
      //! assume ads.example.com should match with example.com as well
      return sDomainA.endsWith(sDomainB) &&
      (sDomainA.length === sDomainB.length ||
        sDomainA.charAt(sDomainA.length - sDomainB.length - 1) === '.');
    };

    //! Url parser for domain fronting to be used
    var urlParserDF = function (sUrl) {
      if (pVn.systemSettings.use_cloudfront_domain === true) {
        var oUrl = new URL(sUrl);
        if (oUrl.href.indexOf(PROXY_API_ENDPOINT) !== -1) {
          oUrl.hostname = PROXY_API_CLOUDFRONT_ENDPOINT;
          sUrl = oUrl.href;
        }

        if (oUrl.href.indexOf(FUSION_AUTH_PRIMARY) !== -1) {
          oUrl.hostname = FUSION_AUTH_SECONDARY;
          sUrl = oUrl.href;
        }
      }
      return sUrl;
    }

    //! Request webservice call
    async function request(sUrl, callback, bSync, sMethod, params) {
      sUrl = urlParserDF(sUrl);

      if (!sMethod || sMethod === "") {
        sMethod = "GET";
      }
      if (!callback || typeof callback !== "function") {
        callback = pVn.nofunc;
      }
      if (!params || params === "") {
        params = "";
      }
      let header = {};
      if (pVn.systemSettings.access_token !== "" &&
        (sUrl.startsWith(SCHEME_SSL + PROXY_API_ENDPOINT) === true ||
          sUrl.startsWith(SCHEME_SSL + PROXY_API_CLOUDFRONT_ENDPOINT) ===
          true)) {
        header = {...header, 'X-Auth-Token': pVn.systemSettings.access_token}
      }
      if (pVn.systemSettings.refresh_token !== "" &&
        (sUrl.startsWith(SCHEME_SSL + PROXY_API_ENDPOINT) === true ||
        sUrl.startsWith(SCHEME_SSL + PROXY_API_CLOUDFRONT_ENDPOINT) === true) &&
          sUrl.indexOf(API_TOKEN_REFRESH) !== -1) {
          header = {...header, 'X-REFRESH-TOKEN': pVn.systemSettings.refresh_token}
      }
      if ((sUrl.startsWith(SCHEME_SSL + PROXY_API_ENDPOINT) === true ||
        sUrl.startsWith(SCHEME_SSL + PROXY_API_CLOUDFRONT_ENDPOINT) === true) &&
          (sUrl.indexOf(API_COUNTRIES_LIST) !== -1 ||
          sUrl.indexOf(API_CHANNELS_LIST) !== -1 ||
        sUrl.indexOf(API_CITIES_LIST) !== -1 ||
        sUrl.indexOf(API_LIST_SERVER) !== -1)) {
        if (sUrl.indexOf(API_COUNTRIES_LIST) !== -1) {
           header = {...header, 'Server-Checksum': pVn.systemSettings.country_checksum}  
        }
        if (sUrl.indexOf(API_CHANNELS_LIST) !== -1) {
          header = {...header,'Server-Checksum': pVn.systemSettings.channel_checksum}  
        }

        if (sUrl.indexOf(API_CITIES_LIST) !== -1) {
          header = {...header,'Server-Checksum': pVn.systemSettings.city_checksum}  
        }
      }
      try {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 6000);
        const response = await fetch(sUrl, {
          method: sMethod,
          timeout: 6000,
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            ...header,
          },
          ...(sMethod !== "GET" && { body: params }),
          signal: controller.signal
        });
        const data = await response.json();
        pVn.isOnline = true;
        var oResult = {
          url: sUrl,
          method: sMethod,
          status: "load",
          code: 1,
          content: JSON.stringify(data),
        };
        callback(oResult);
      } catch (e) {
        //console.log(e);
        pVn.isOnline = false;
        callback(false);
      }
    }

    return {
      getUrl: get,
      request: request,
      getHost: getHost,
      getDomain: getDomain,
      domainMatch: domainMatch,
      urlParserDF: urlParserDF
    };
  })();
})();
