var result;

// Broadcast reloadComplete back to the extension
window.addEventListener('load', function (e) {
  if (isOnASharePointPage === undefined) {
    isOnASharePointPage =
      $("meta[name='GENERATOR'][content='Microsoft SharePoint']")[0] !== undefined ||
      $("meta[name='GENERATOR'][content='Microsoft SharePoint (Service worker)']")[0] !== undefined;
  }

  if (!isOnASharePointPage) {
    sendDisablingCommand();
    return;
  } else {
    isOnClassicSharePoint = !!(window.MSOWebPartPageFormName && document.forms[MSOWebPartPageFormName]);
    sendIsClassic();
  }

  if (false) {
    // need logic here that knows whether or not we've run the tool yet.
    return;
  }

  result = new PageListenerResult();
  var loadPromises = [];

  loadPromises.push(
    new Promise(function (resolve, reject) {
      if (window._spPageContextInfo) {
        setTimeout(() => {
          setPageContext().then(() => resolve());
        }, 0);
      } else {
        reject();
      }
    })
  );

  loadPromises.push(
    new Promise(function (resolve, reject) {
      setTimeout(() => {
        result.cbqWebpartExists = checkForCBQWebpart();
        resolve();
      }, 0);
    })
  );

  loadPromises.push(
    new Promise(function (resolve, reject) {
      setTimeout(() => {
        if (window._spPageContextInfo) {
          var siteId = window._spPageContextInfo.siteId;
          var webId = window._spPageContextInfo.webId;
          var pageListId = window._spPageContextInfo.pageListId;
          var pageItemId = window._spPageContextInfo.pageItemId;
          if (siteId && webId && pageListId && pageItemId) {
            var pageUniqueId = siteId + ':' + webId + ':' + pageListId + ':' + pageItemId;
            result.pageUniqueId = pageUniqueId;
            resolve();
          } else {
            reject();
          }
        } else {
          reject();
        }
      }, 0);
    })
  );

  loadPromises.push(
    new Promise(function (resolve, reject) {
      setTimeout(() => {
        if (window.g_duration !== undefined) {
          result.spRequestDuration = window.g_duration;
        }
        if (window.g_iisLatency !== undefined) {
          result.spIISLatency = window.g_iisLatency;
        }
        resolve();
      }, 0);
    })
  );

  Promise.all(loadPromises).then(
    () => {
      deliverResult();
    },
    () => {
      deliverResult();
    }
  );
});

function deliverResult() {
  let pageLoadTime = window.performance.timing.loadEventEnd - window.performance.timing.navigationStart;
  result.pageLoadTime = pageLoadTime;
  var event = new CustomEvent('SP-YSLOW-LOAD', {
    detail: result
  });
  document.dispatchEvent(event);
}

function setPageContext() {
  //var pageContext = Object.assign({}, window._spPageContextInfo);

  // security boundry prevents sending window objects to the content script
  // populate new object with useful parts of _spPageContextInfo

  result.pageContext.CorrelationId = window._spPageContextInfo.CorrelationId;
  result.pageContext.DesignPackageId = window._spPageContextInfo.DesignPackageId;
  result.pageContext.farmLabel = window._spPageContextInfo.farmLabel;
  result.pageContext.groupColor = window._spPageContextInfo.groupColor;
  result.pageContext.groupHasHomepage = window._spPageContextInfo.groupHasHomepage;
  result.pageContext.hasManageWebPermissions = window._spPageContextInfo.hasManageWebPermissions;
  result.pageContext.isNoScriptEnabled = window._spPageContextInfo.isNoScriptEnabled;
  result.pageContext.isSiteAdmin = window._spPageContextInfo.isSiteAdmin;
  result.pageContext.isSPO = window._spPageContextInfo.isSPO;
  result.pageContext.isWebWelcomePage = window._spPageContextInfo.isWebWelcomePage;
  result.pageContext.listId = window._spPageContextInfo.listId;
  result.pageContext.listPermsMask = window._spPageContextInfo.listPermsMask;
  result.pageContext.pagePermsMask = window._spPageContextInfo.pagePermsMask;
  result.pageContext.PreviewFeaturesEnabled = window._spPageContextInfo.PreviewFeaturesEnabled;
  result.pageContext.PublishingFeatureOn = window._spPageContextInfo.PublishingFeatureOn;
  result.pageContext.sitePagesEnabled = window._spPageContextInfo.sitePagesEnabled;
  result.pageContext.siteSubscriptionId = window._spPageContextInfo.siteSubscriptionId;
  result.pageContext.themedCssFolderUrl = window._spPageContextInfo.themedCssFolderUrl;
  result.pageContext.webPermsMask = window._spPageContextInfo.webPermsMask;
  result.pageContext.webTemplate = window._spPageContextInfo.webTemplate;
  result.pageContext.webUIVersion = window._spPageContextInfo.webUIVersion;

  return Promise.resolve();
}

function checkForCBQWebpart() {
  return !!$('.cbq-layout-main').length;
}

class PageListenerResult {
  constructor() {
    this.pageContext = {};
    this.perfEntries = {};
    this.csomInfo = {};
    this.cbqWebpartExists = false;
    this.pageLoadTime = -1;
    this.pageUniqueId = '';
    this.spRequestDuration = -1;
    this.spIISLatency = -1;
  }
}

window.addEventListener('beforeunload', function (e) {
  document.dispatchEvent(new CustomEvent('SP-YSLOW-WINDOW-UNLOAD'));
});
