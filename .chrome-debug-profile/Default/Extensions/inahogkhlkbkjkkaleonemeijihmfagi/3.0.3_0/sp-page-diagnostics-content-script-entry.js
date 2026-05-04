// -----------------------------------------------------------------------
// <copyright company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>
// -----------------------------------------------------------------------

(() => {
  const loadContentScriptCore = () => {
    chrome.runtime.sendMessage({
      type: 'AddContentScript',
      data: {}
    });
  };

  chrome.runtime.sendMessage({ type: 'GetBackgroundStateRequest' }, (response) => {
    const content = response.data;
    if (!content) {
      return;
    }

    if (content.state !== 'Initial') {
      loadContentScriptCore();
      if (content.data.pageType === 'ModernPage') {
        const element = document.head || document.documentElement;
        const injectedScript = document.createElement('script');
        injectedScript.src = chrome.runtime.getURL('modern-injected-script.js');
        element.appendChild(injectedScript);
      } else if (content.data.pageType === 'ClassicPage') {
        const element = document.head || document.documentElement;
        const injectedScript = document.createElement('script');
        injectedScript.src = chrome.runtime.getURL('classic-injected-script.js');
        element.appendChild(injectedScript);
        const jquery = document.createElement('script');
        jquery.src = chrome.runtime.getURL('classic/jquery/jquery.min.js');
        element.appendChild(jquery);

        const pageNetwork = document.createElement('script');
        pageNetwork.src = chrome.runtime.getURL('classic/contentScript/pageNetwork.js');
        element.appendChild(pageNetwork);

        const listener = document.createElement('script');
        listener.src = chrome.runtime.getURL('classic/contentScript/registerListener.js');
        element.appendChild(listener);
      }
    }

    if (content.state === 'Initial') {
      const isOnSharePointPage =
        document.querySelectorAll("meta[name='GENERATOR'][content='Microsoft SharePoint']")[0] !==
          undefined ||
        document.querySelectorAll(
          "meta[name='GENERATOR'][content='Microsoft SharePoint (Service worker)']"
        )[0] !== undefined;

      document.onreadystatechange = (event) => {
        if (document.readyState === 'complete') {
          if (isOnSharePointPage) {
            if (!window.__PDT__CONTENT__SCRIPT) {
              loadContentScriptCore();
            }

            window.__PDT__CONTENT__SCRIPT = true;
          } else {
            chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
              if (message.type === 'SYN') {
                sendResponse({ type: 'ACK' });
                return true;
              }

              if (message.type === 'GetPageInfoRequest') {
                const data = {
                  pageType: 'NotSupported',
                  pageEnvironment: 'UnKnown',
                  pageMode: 'View',
                  siteType: 'Unknown',
                  isPageCheckedOutToCurrentUser: false
                };

                sendResponse({ type: 'GetPageInfoResponse', data });
                return true;
              }
            });
          }
        }
      };
    }
  });
})();
