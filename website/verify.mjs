import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs'
import { dirname, resolve, join, relative, isAbsolute } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
const root = resolve(dirname(fileURLToPath(import.meta.url)), 'dist')
const manifest = JSON.parse(readFileSync(join(root, 'build-manifest.json'), 'utf8'))
const bytes = readFileSync(join(root, manifest.archive))
if (bytes.readUInt32LE(0) !== 0x04034b50) throw new Error('Download is not a ZIP archive.')
if (createHash('sha256').update(bytes).digest('hex') !== manifest.sha256) throw new Error('Download hash mismatch.')
let pages = 0, links = 0
function scan(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) scan(path)
    else if (entry.name.endsWith('.html')) {
      pages++
      const html = readFileSync(path, 'utf8')
      if (!html.includes('lang="zh-CN"')) throw new Error('Missing page language: ' + path)
      for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
        const href = match[1].replace(/&amp;/g, '&')
        if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(href)) continue
        const [target, hash] = href.split('#')
        const clean = decodeURIComponent(target.split('?')[0])
        const dest = clean.startsWith(manifest.base) ? resolve(root, clean.slice(manifest.base.length)) : resolve(dirname(path), clean || entry.name)
        const local = relative(root, dest)
        if (local.startsWith('..') || isAbsolute(local)) throw new Error('Link escaped output: ' + href)
        if (!existsSync(dest) || !statSync(dest).isFile()) throw new Error('Broken local link: ' + href + ' in ' + path)
        if (hash && dest.endsWith('.html')) {
          const ids = new Set([...readFileSync(dest, 'utf8').matchAll(/\bid="([^"]+)"/g)].map(m => m[1]))
          if (!ids.has(decodeURIComponent(hash))) throw new Error('Missing heading: ' + href + ' in ' + path)
        }
        links++
      }
    }
  }
}
scan(root)
console.log('Verified ' + pages + ' pages, ' + links + ' local links, and versioned source ZIP.')

