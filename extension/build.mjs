// Bundles src/*.js into js/*.js so Chrome can load them.
// The js/ folder is committed, so the extension loads without running this;
// re-run `npm run build` after changing anything in src/.
import { build } from "esbuild";

await build({
  entryPoints: ["src/background.js", "src/content.js", "src/sidepanel.js", "src/options.js"],
  outdir: "js",
  bundle: true,
  format: "iife",
  target: "chrome116",
  legalComments: "none",
  logLevel: "info",
});
