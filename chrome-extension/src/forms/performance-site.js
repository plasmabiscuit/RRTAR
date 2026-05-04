(function registerPerformanceSiteAutofill() {
  self.RRTARPerformanceSiteAutofill = {
    run(manifest) {
      const entries = Array.isArray(manifest) ? manifest : [];
      return Promise.resolve({
        ok: false,
        error: "Performance Site autofill is not ported yet.",
        details: {
          manifestEntries: entries.length,
          sourceScript: "scripts/automate_performance_site.py",
          iframePattern: "PerformanceSite_4_0",
        },
      });
    },
  };
})();
