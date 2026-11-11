// The page's own rules on top of the usual ones: what the security policy refuses (deploy/Caddyfile.staff-login)
// must not be written in the first place. tests/test_staff_ui.py checks the same in the source and the build.
import js from "@eslint/js";
import hooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["node_modules"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": hooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "no-restricted-syntax": [
        "error",
        { selector: "JSXAttribute[name.name='style']", message: "No style attribute: the policy refuses inline styles." },
        { selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']", message: "Text only: never HTML from the server." },
        { selector: "MemberExpression[property.name='innerHTML']", message: "Text only." },
        { selector: "MemberExpression[property.name='style']", message: "No inline styles: use a class." },
        { selector: "CallExpression[callee.name=/^(alert|confirm|prompt)$/]", message: "Use the in-page confirm step." },
        { selector: "MemberExpression[object.name='localStorage']", message: "Nothing is kept in the browser." },
      ],
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);
