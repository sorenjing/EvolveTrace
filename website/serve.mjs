import { createServer } from 'node:http'
import { readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve, relative, isAbsolute, extname } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = join(dirname(fileURLToPath(import.meta.url)), 'dist')
const port = Number(process.env.PORT || 5181)
const mime = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.svg':'image/svg+xml', '.zip':'application/zip', '.json':'application/json', '.sha256':'text/plain; charset=utf-8' }
createServer((req, res) => {
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname)
    const file = resolve(root, '.' + path + (path.endsWith('/') ? 'index.html' : ''))
    const local = relative(root, file)
    if (local.startsWith('..') || isAbsolute(local) || !statSync(file).isFile()) throw new Error('Not found')
    res.writeHead(200, { 'Content-Type':mime[extname(file)] || 'application/octet-stream', 'X-Content-Type-Options':'nosniff' })
    res.end(readFileSync(file))
  } catch { res.writeHead(404, { 'Content-Type':'text/plain; charset=utf-8' }); res.end('页面未找到') }
}).listen(port, '127.0.0.1', () => console.log('Preview: http://127.0.0.1:' + port))

