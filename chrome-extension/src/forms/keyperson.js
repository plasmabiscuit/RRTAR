(function registerKeyPersonAutofill() {
  self.RRTARKeyPersonAutofill = {
    run(manifest) {
      const entries = Array.isArray(manifest) ? manifest : [];
      return Promise.resolve({
        ok: false,
        error: "Key Person autofill is not ported yet.",
        details: {
          manifestEntries: entries.length,
          sourceScript: "scripts/automate.py",
          iframePattern: "RR_KeyPersonExpanded_4_0",
        },
      });
    },
  };
})();
