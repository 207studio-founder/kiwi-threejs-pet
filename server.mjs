// Local static server + frame sink. Binds to 127.0.0.1 only; writes only under ./export.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const EXPORT = path.join(ROOT, 'export');
const PORT = +(process.env.PORT || 5173);
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.webp': 'image/webp', '.css': 'text/css', '.md': 'text/markdown' };
const SAFE = /^[A-Za-z0-9_.-]+$/;

http.createServer((req, res) => {
  const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (req.method === 'POST' && url.startsWith('/api/export/')) {
    const [dir, name] = url.slice('/api/export/'.length).split('/');
    if (!SAFE.test(dir || '') || !SAFE.test(name || '') || !/\.(png|json)$/.test(name)) { res.writeHead(400).end(); return; }
    fs.mkdirSync(path.join(EXPORT, dir), { recursive: true });
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => { fs.writeFileSync(path.join(EXPORT, dir, name), Buffer.concat(chunks)); res.writeHead(204).end(); });
    return;
  }
  if (req.method === 'POST' && url.startsWith('/api/codex/stage/')) {
    const [dir, name] = url.slice('/api/codex/stage/'.length).split('/');
    if (!SAFE.test(dir || '') || !SAFE.test(name || '') || !name.endsWith('.png')) { res.writeHead(400).end(); return; }
    const out = path.join(EXPORT, 'codex-v2', 'stage', dir);
    fs.mkdirSync(out, { recursive: true });
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => { fs.writeFileSync(path.join(out, name), Buffer.concat(chunks)); res.writeHead(204).end(); });
    return;
  }
  if (req.method === 'POST' && url === '/api/codex/build') {
    // local build only: downsample + assemble + validate (tools/build_codex.py)
    const log = path.join(EXPORT, 'codex-v2', 'build.log');
    execFile(path.join(ROOT, '.venv/bin/python'), [path.join(ROOT, 'tools/build_codex.py')], { cwd: ROOT, maxBuffer: 1 << 24 },
      (err, stdout, stderr) => {
        const exit = err ? (err.code ?? 1) : 0;
        fs.writeFileSync(log, `${stdout}\n${stderr}`);
        fs.writeFileSync(`${log}.exit`, `${exit}\n`);
        res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ exit, tail: `${stdout}${stderr}`.slice(-3000) }));
      });
    return;
  }
  const file = path.normalize(path.join(ROOT, url === '/' ? 'index.html' : url));
  if (!file.startsWith(ROOT + path.sep) || file.includes(`${path.sep}.venv`)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(data);
  });
}).listen(PORT, '127.0.0.1', () => console.log(`Kiwi: http://127.0.0.1:${PORT}/`));
