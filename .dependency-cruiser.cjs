/** Dependency boundaries for the two TypeScript apps (site/, staff-ui/). Run: `make depcruise`. */
module.exports = {
  forbidden: [
    {
      name: "no-circular",
      severity: "error",
      comment: "A cycle makes the modules in it impossible to load or test apart. Move the shared part to a third module both import.",
      from: {},
      to: { circular: true },
    },
    {
      name: "apps-are-separate",
      severity: "error",
      comment: "site/ and staff-ui/ ship separately. Share nothing by import; copy it or move it to a file both read as data.",
      from: { path: "^site/" },
      to: { path: "^staff-ui/" },
    },
    {
      name: "apps-are-separate-reverse",
      severity: "error",
      comment: "site/ and staff-ui/ ship separately. Share nothing by import; copy it or move it to a file both read as data.",
      from: { path: "^staff-ui/" },
      to: { path: "^site/" },
    },
    {
      name: "no-test-imports-in-app-code",
      severity: "error",
      comment: "App code must not import a test file. Move what both need to a non-test module.",
      from: { pathNot: "(\\.test\\.|\\.spec\\.|/e2e/)" },
      to: { path: "(\\.test\\.|\\.spec\\.)" },
    },
  ],
  options: {
    tsConfig: { fileName: "site/tsconfig.json" },
    doNotFollow: { path: "node_modules" },
    exclude: { path: "(^|/)(node_modules|\\.next|out|dist)/" },
    moduleSystems: ["es6", "cjs"],
  },
};
