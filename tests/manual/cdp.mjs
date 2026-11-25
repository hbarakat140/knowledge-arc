// usage: node cdp.mjs <url> <js-after-load-1> [<js-2> ...]  -> prints each evaluation result
import { spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const [url, ...steps] = process.argv.slice(2);
const port = 9333;
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',
  ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'cdp-'))}`, '--no-first-run', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) { await sleep(200); try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page'); } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pending = {};
ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
const send = (method, params = {}) => new Promise(r => { pending[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
await send('Page.enable'); await send('Runtime.enable');
await send('Page.navigate', { url }); await sleep(2500);
for (const js of steps) {
  const r = await send('Runtime.evaluate', { expression: js, awaitPromise: true, returnByValue: true });
  console.log('>>', JSON.stringify(r.result?.result?.value ?? r.result));
  await sleep(1500);
}
ws.close(); chrome.kill();
