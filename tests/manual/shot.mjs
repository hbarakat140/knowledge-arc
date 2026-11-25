// usage: node shot.mjs <url> <out.png> [js to run after load] -> prints document.title (and js result), saves a screenshot
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const [url, out, js] = process.argv.slice(2);
const port = 9334;
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',
  ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'cdp-'))}`,
   '--no-first-run', '--window-size=1100,800', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) { await sleep(200); try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page'); } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pending = {};
ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
const send = (method, params = {}) => new Promise(r => { pending[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
await send('Page.enable'); await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1100, height: 800, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url }); await sleep(4000);
if (js) { const r = await send('Runtime.evaluate', { expression: js, awaitPromise: true, returnByValue: true }); console.log('>> js', JSON.stringify(r.result?.result?.value ?? r.result)); await sleep(2000); }
const t = await send('Runtime.evaluate', { expression: 'document.title', returnByValue: true });
console.log('>> title', t.result?.result?.value);
const s = await send('Page.captureScreenshot', { format: 'png' });
writeFileSync(out, Buffer.from(s.result.data, 'base64'));
ws.close(); chrome.kill();
