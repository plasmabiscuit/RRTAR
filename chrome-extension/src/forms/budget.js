(function registerBudgetAutofill() {
  self.RRTARBudgetAutofill = {
    run(manifest) {
      const entries = Array.isArray(manifest) ? manifest : [];
      return Promise.resolve({
        ok: false,
        error: "Budget autofill is not ported yet.",
        details: {
          manifestEntries: entries.length,
          sourceScript: "scripts/automate_budget.py",
          iframePattern: "RR_Budget_3_0",
        },
      });
    },
  };
})();
