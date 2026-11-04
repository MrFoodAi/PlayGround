const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.env.PORT || 3000);
const ROOT = path.join(__dirname, 'dist');

const mime = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

const server = http.createServer((req, res) => {
  let filePath = path.join(ROOT, path.normalize(decodeURIComponent(req.url || '/')));
  const resolvedRoot = path.resolve(ROOT);
  const resolvedFile = path.resolve(filePath);
  if (resolvedFile !== resolvedRoot && !resolvedFile.startsWith(resolvedRoot + path.sep)) {
    res.writeHead(403); res.end('Forbidden'); return;
  }
  try {
    if (fs.statSync(resolvedFile).isDirectory()) {
      filePath = path.join(resolvedFile, 'index.html');
    }
  } catch {
    filePath = path.join(resolvedRoot, 'index.html');
  }
  fs.readFile(filePath, (err, content) => {
    if (err) {
      if (filePath !== path.join(resolvedRoot, 'index.html')) {
        fs.readFile(path.join(resolvedRoot, 'index.html'), (err2, html) => {
          if (err2) { res.writeHead(404); res.end('Not found'); return; }
          res.writeHead(200, { 'Content-Type': mime['.html'], 'Cache-Control': 'no-cache' });
          res.end(html);
        });
      } else {
        res.writeHead(404); res.end('Not found');
      }
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': mime[ext] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
    res.end(content);
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[server] GoldAI XAU Bot serving ${ROOT} on http://0.0.0.0:${PORT}`);
});
