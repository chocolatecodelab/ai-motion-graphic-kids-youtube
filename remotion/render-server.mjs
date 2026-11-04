// render-server: long-lived Node process used by the Python pipeline (factory.media.remotion).
// Bundles webpack ONCE (cached per source hash in .bundle/<key>) and keeps ONE browser for
// every scene, instead of `remotion render` per scene (bundle + Chrome cold start each time).
// Ported from ai-video-editor-remotion (same owner); output changed to H.264 scene clips.
//
// Usage (by Python):  node render-server.mjs --bundle .bundle/<key>
// Protocol: stdin one JSON per line {id, composition, props, out, scale, crf}
//           stdout lines prefixed "@@J " + JSON: {ready} | {id, ok, error?, ms}
// Remotion/Chrome logs go to stderr so stdout carries only the protocol.
import { bundle } from "@remotion/bundler";
import { ensureBrowser, openBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";

console.log = (...a) => console.error(...a);
const send = (obj) => process.stdout.write(`@@J ${JSON.stringify(obj)}\n`);

const DIR = path.dirname(fileURLToPath(import.meta.url));
const arg = process.argv.indexOf("--bundle");
if (arg < 0) {
  console.error("need --bundle <dir>");
  process.exit(2);
}
const bundleDir = path.resolve(DIR, process.argv[arg + 1]);

const prepareBundle = async () => {
  if (fs.existsSync(path.join(bundleDir, "index.html"))) return bundleDir;
  const tmp = `${bundleDir}.tmp`;
  fs.rmSync(tmp, { recursive: true, force: true });
  await bundle({ entryPoint: path.join(DIR, "src", "index.ts"), outDir: tmp, publicDir: path.join(DIR, "public"),
                 rootDir: DIR, enableCaching: true });
  // Older bundles (different source hash) are never used again: delete them.
  for (const d of fs.readdirSync(path.dirname(bundleDir))) {
    const p = path.join(path.dirname(bundleDir), d);
    if (p !== tmp && p !== bundleDir && fs.statSync(p).isDirectory()) fs.rmSync(p, { recursive: true, force: true });
  }
  fs.renameSync(tmp, bundleDir);
  return bundleDir;
};

const serveUrl = await prepareBundle();
const browserExecutable = process.env.REMOTION_CHROME || null;
await ensureBrowser({ browserExecutable });
const browser = await openBrowser("chrome", { browserExecutable, logLevel: "error" });

const render = async ({ composition: id, props, out, scale = 1, crf = 20 }) => {
  const composition = await selectComposition({ serveUrl, id, inputProps: props, puppeteerInstance: browser,
                                                logLevel: "error" });
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const tmpOut = `${out}.part.mp4`;
  await renderMedia({
    composition, serveUrl, inputProps: props, puppeteerInstance: browser, outputLocation: tmpOut, overwrite: true,
    codec: "h264", crf, pixelFormat: "yuv420p", imageFormat: "jpeg", jpegQuality: 90, colorSpace: "bt709",
    scale, muted: true, logLevel: "error",
  });
  fs.renameSync(tmpOut, out); // atomic: a half-written file never looks finished
};

// Sequential queue: one scene at a time (renderMedia already renders frames in parallel).
let queue = Promise.resolve();
const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line) => {
  if (!line.trim()) return;
  queue = queue.then(async () => {
    let req;
    const t0 = Date.now();
    try {
      req = JSON.parse(line);
      await render(req);
      send({ id: req.id, ok: true, ms: Date.now() - t0 });
    } catch (e) {
      send({ id: req?.id ?? null, ok: false, error: String(e?.stack ?? e), ms: Date.now() - t0 });
    }
  });
});
rl.on("close", () => {
  queue.finally(async () => {
    await browser.close({ silent: true }).catch(() => undefined);
    process.exit(0);
  });
});
send({ ready: true });
