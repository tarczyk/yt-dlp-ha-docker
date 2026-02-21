const http = require('http');
const { exec } = require('child_process');

const PORT = process.env.PORT || 3000;
const DOWNLOAD_DIR = '/media/youtube_downloads';

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/download') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      let url;
      try {
        url = JSON.parse(body).url;
      } catch {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
        return;
      }
      if (!url) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Missing url' }));
        return;
      }
      exec(`yt-dlp -o "${DOWNLOAD_DIR}/%(title)s.%(ext)s" -- "${url}"`, (err, stdout, stderr) => {
        if (err) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: stderr }));
          return;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', output: stdout }));
      });
    });
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  }
});

server.listen(PORT, () => {
  console.log(`yt-dlp-ha-docker listening on port ${PORT}`);
});
