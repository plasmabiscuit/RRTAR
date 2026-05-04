class StackEntry {
  constructor(stack, url) {
    this.stack = stack;
    this.url = url;
  }
}

var isOnASharePointPage;
var isOnClassicSharePoint;
var isOnEdge;
var WINDOW_PERF_DELAY = 2000;

XMLHttpRequest.prototype.actualOpen = XMLHttpRequest.prototype.open;

var newOpen = function (method, url, async, user, password) {
  if (isOnASharePointPage === undefined) {
    isOnASharePointPage =
      $("meta[name='GENERATOR'][content='Microsoft SharePoint']")[0] !== undefined ||
      $("meta[name='GENERATOR'][content='Microsoft SharePoint (Service worker)']")[0] !== undefined;

    if (!isOnASharePointPage) {
      sendDisablingCommand();
    } else {
      isOnClassicSharePoint = !!(window.MSOWebPartPageFormName && document.forms[MSOWebPartPageFormName]);
      sendIsClassic();
    }
  }

  if (isOnEdge === undefined) {
    isOnEdge = window.navigator.userAgent.indexOf('Edge') > -1;
  }

  // bypass for CSOM calls
  if (url.includes('_vti_bin/client.svc') || isOnASharePointPage === false || isOnEdge) {
    this.actualOpen(method, url, async, user, password);
    return;
  }

  var caller = arguments.callee.caller;
  var requestStack = [];
  var count = 0;

  // record the call stack
  while (caller) {
    if (count > 10) {
      debugger;
      break;
    }
    requestStack.push(caller.name);
    caller = caller.caller;
    count++;
  }

  if (count > 10) {
    // too deep in the hole. return out
    this.actualOpen(method, url, async, user, password);
    return;
  }

  this.onreadystatechange = function () {
    if (this.readyState === XMLHttpRequest.DONE) {
      var perfPayload = assemblePerfPayload();

      var event = new CustomEvent('SP-YSLOW-WINDOW-PERF', {
        detail: {
          perfPayload: perfPayload
        }
      });

      document.dispatchEvent(event);
    }
  };

  var entryUrl = url;
  if (entryUrl.startsWith('/')) {
    // ensure that calls with relative urls are recorded consistently
    entryUrl = window.location.origin + entryUrl;
  }

  let entryStack = requestStack.filter(function (fnName) {
    return fnName.length > 0;
  });

  if (entryStack.length > 0) {
    var stackEntry = new StackEntry(requestStack, entryUrl);
    sendCallStack(stackEntry);
  }

  // call the actual XHR method
  this.actualOpen(method, url, async, user, password);
};

var sendCallStack = function (stackEntry) {
  const event = new CustomEvent('SP-YSLOW-CALLSTACK', {
    detail: {
      stack: stackEntry.stack,
      url: stackEntry.url
    }
  });

  document.dispatchEvent(event);
};

var sendDisablingCommand = function () {
  const event = new CustomEvent('SP-YSLOW-DISABLE');
  document.dispatchEvent(event);
};

var sendIsClassic = function () {
  const event = new CustomEvent('SP-YSLOW-IS-CLASSIC', {
    detail: {
      isClassic: isOnClassicSharePoint
    }
  });

  document.dispatchEvent(event);
};

// this comment disables callstacks entirely
// XMLHttpRequest.prototype.open = newOpen;

// while callstacks are disabled, send up perf info every 10 seconds
setInterval(function () {
  const perfPayload = assemblePerfPayload();

  const event = new CustomEvent('SP-YSLOW-WINDOW-PERF', {
    detail: {
      perfPayload: perfPayload
    }
  });

  document.dispatchEvent(event);
}, 10000);

function assemblePerfPayload() {
  console.log('Copying network performance info...');

  return window.performance
    .getEntries()
    .map(function (elem) {
      if (elem.name.startsWith('http')) {
        return elem.toJSON();
      } else {
        return undefined;
      }
    })
    .filter(function (elem) {
      return elem !== undefined;
    });
}
