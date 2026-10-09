import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, posix, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import MarkdownIt from 'markdown-it'
import anchor from 'markdown-it-anchor'
import project from './project.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const out = join(here, 'dist')
const base = process.env.WEBSITE_BASE || '/'
if (!/^\/(?:[a-zA-Z0-9_-]+\/)*$/.test(base)) throw new Error('WEBSITE_BASE must be / or a slash-terminated path.')
if (existsSync(out) && lstatSync(out).isSymbolicLink()) throw new Error('dist must not be a symlink.')
const git = (...args) => execFileSync('git', ['-C', root, ...args], { encoding: 'utf8' }).trim()
const revision = git('rev-parse', 'HEAD')
const short = revision.slice(0, 7)
const tracked = new Set(git('ls-tree', '-r', '--name-only', revision).split('\n'))
const url = path => base + path
const escape = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
const sourceURL = path => project.repository + '/blob/' + revision + '/' + path.split('/').map(encodeURIComponent).join('/')
const releaseURL = project.repository + '/releases'
const docs = project.documents
const docsBySource = new Map(docs.map(doc => [doc.source, 'docs/' + doc.slug + '.html']))
const archive = project.id + '-' + short + '-source.zip'
const sourceCommand = project.installCommand?.replaceAll('{revision}', revision) || './start.ps1'
const peer = process.env.COMPANION_SITE_URL || project.companion.repository

rmSync(out, { recursive: true, force: true })
mkdirSync(join(out, 'downloads'), { recursive: true })
mkdirSync(join(out, 'docs'), { recursive: true })
mkdirSync(join(out, 'assets'), { recursive: true })
cpSync(join(here, 'assets'), join(out, 'assets'), { recursive: true })
execFileSync('git', ['-C', root, 'archive', '--format=zip', '--prefix=' + project.id + '/', '--output=' + join(out, 'downloads', archive), revision])
const bytes = readFileSync(join(out, 'downloads', archive))
const hash = createHash('sha256').update(bytes).digest('hex')
writeFileSync(join(out, 'downloads', archive + '.sha256'), hash + '  ' + archive + '\n')
const manifest = { project: project.title, source_revision: revision, archive: 'downloads/' + archive, sha256: hash, bytes: bytes.length, base, documentation: docs.map(doc => doc.source) }
writeFileSync(join(out, 'build-manifest.json'), JSON.stringify(manifest, null, 2) + '\n')

const md = new MarkdownIt({ html: false, linkify: true }).use(anchor, {
  slugify: title => title.trim().toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s+/g, '-')
})
const originalLink = md.renderer.rules.link_open || ((tokens, index, options, env, self) => self.renderToken(tokens, index, options))
md.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index]
  const href = token.attrGet('href') || ''
  if (env.source && href && !/^(?:[a-z][a-z0-9+.-]*:|\/|#)/i.test(href)) {
    const match = href.match(/^([^?#]*)(.*)$/)
    const path = posix.normalize(posix.join(posix.dirname(env.source), decodeURIComponent(match[1])))
    token.attrSet('href', docsBySource.has(path) ? url(docsBySource.get(path)) + match[2] : sourceURL(path) + match[2])
  }
  return originalLink(tokens, index, options, env, self)
}
const originalImage = md.renderer.rules.image
md.renderer.rules.image = (tokens, index, options, env, self) => {
  const token = tokens[index]
  const src = token.attrGet('src') || ''
  if (env.source && src && !/^(?:[a-z][a-z0-9+.-]*:|\/)/i.test(src)) {
    const path = posix.normalize(posix.join(posix.dirname(env.source), src))
    if (!tracked.has(path)) throw new Error('Untracked documentation image: ' + path)
    token.attrSet('src', project.repository.replace('https://github.com/', 'https://raw.githubusercontent.com/') + '/' + revision + '/' + path)
  }
  return originalImage(tokens, index, options, env, self)
}

const code = (command, caption = '') => '<div class="command">' + (caption ? '<div class="command-label">' + escape(caption) + '</div>' : '') + '<pre><code>' + escape(command) + '</code></pre></div>'
const button = (label, href, primary = false, download = false) => '<a class="button ' + (primary ? 'primary' : 'secondary') + '" href="' + escape(href) + '"' + (download ? ' download' : '') + '>' + escape(label) + '</a>'
const nav = (path, label, page) => '<a href="' + url(path) + '"' + (page === path ? ' aria-current="page"' : '') + '>' + label + '</a>'
function layout(title, body, page, description = project.description) {
  return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<meta name="description" content="' + escape(description) + '"><title>' + escape(title === project.title ? title : title + ' · ' + project.title) + '</title>' +
    '<link rel="icon" href="' + url('assets/icon.svg') + '"><link rel="stylesheet" href="' + url('assets/style.css') + '"><script src="' + url('assets/app.js') + '" defer></script></head>' +
    '<body data-theme="' + project.theme + '"><a class="skip-link" href="#main">跳到正文</a><header class="site-header"><div class="header-inner">' +
    '<a class="brand" href="' + url('index.html') + '"><span class="brand-mark" aria-hidden="true">' + project.mark + '</span>' + project.title + '</a>' +
    '<button class="menu-toggle" aria-controls="site-nav" aria-expanded="false">菜单</button><nav id="site-nav" class="site-nav" aria-label="主导航">' +
    nav('index.html', '首页', page) + nav('getting-started.html', '快速开始', page) + nav('docs/index.html', '文档', page) + nav('download.html', '下载', page) + nav('changelog.html', '更新记录', page) +
    '<a href="' + project.repository + '">GitHub</a></nav></div></header><main id="main">' + body + '</main>' +
    '<footer class="site-footer"><div><strong>' + project.title + '</strong><p>' + escape(project.footer) + '</p></div><div><a href="' + sourceURL('LICENSE') + '">' + escape(project.license) + '</a><a href="' + escape(peer) + '">' + project.companion.title + '</a><a href="' + releaseURL + '">GitHub Releases</a></div></footer>' +
    '<div class="copy-status sr-only" role="status" aria-live="polite"></div></body></html>'
}
function save(path, title, content) { writeFileSync(join(out, path), layout(title, content, path)) }
const facts = project.features.map((feature, i) => '<article class="feature"><span class="ordinal">0' + (i + 1) + '</span><h3>' + escape(feature.title) + '</h3><p>' + escape(feature.text) + '</p></article>').join('')
save('index.html', project.title,
  '<section class="hero"><div class="hero-copy"><p class="eyebrow">' + project.eyebrow + '</p><h1>' + project.headline + '</h1><p class="lead">' + project.description + '</p><div class="actions">' +
  button('开始使用', url('getting-started.html'), true) + button('下载源码 ZIP', url('downloads/' + archive), false, true) + '</div><p class="hero-meta">' + project.license + ' <span>·</span> 本地优先 <span>·</span> 源码 ' + short + '</p></div>' + project.diagram +
  '</section><section class="section"><div class="section-heading"><p class="eyebrow">CAPABILITIES</p><h2>从问题到可用的工作流</h2></div><div class="features">' + facts + '</div></section>' +
  '<section class="section split"><div><p class="eyebrow">QUICK START</p><h2>' + project.startTitle + '</h2><p>' + project.startDescription + '</p>' + button('查看完整安装步骤', url('getting-started.html')) + '</div>' + code(sourceCommand, project.commandCaption) + '</section>' +
  '<section class="section integration"><p class="eyebrow">BETTER TOGETHER</p><h2>上下文与执行证据，衔接起来。</h2><p>' + project.companion.text + '</p><div class="integration-flow"><span>AI Context Kit<small>准备上下文与任务契约</small></span><span class="flow-separator" aria-hidden="true">/</span><span>EvolveTrace<small>记录执行、评估与人工复核</small></span></div>' +
  button('了解 ' + project.companion.title, peer) + '</section>' +
  '<section class="section boundary"><div><h2>当前可用</h2><p>' + project.available + '</p></div><div><h2>后续计划</h2><p>' + project.planned + '</p></div></section>')
save('getting-started.html', '快速开始', '<section class="page-heading"><p class="eyebrow">GET STARTED</p><h1>快速开始</h1><p class="lead">' + project.startDescription + '</p></section><div class="article-wrap"><article class="prose">' + md.render(project.quickStart.replaceAll('{revision}', revision)) + '</article></div>')
save('docs/index.html', '文档', '<section class="page-heading"><p class="eyebrow">DOCUMENTATION</p><h1>按你当前的任务阅读</h1><p class="lead">从安装到日常使用，再到集成与排障。正文直接来自项目文档。</p></section><section class="document-grid">' +
  docs.map(doc => '<a class="document-card" href="' + url('docs/' + doc.slug + '.html') + '"><span class="eyebrow">' + escape(doc.group) + '</span><h2>' + escape(doc.title) + '</h2><p>' + escape(doc.description) + '</p><span class="text-link">阅读文档</span></a>').join('') + '</section>')
for (const doc of docs) {
  if (!tracked.has(doc.source)) throw new Error('Document must be committed: ' + doc.source)
  // Documentation and the download must describe the same committed source.
  const text = git('show', revision + ':' + doc.source)
  const env = { source: doc.source }
  const tokens = md.parse(text, env)
  const html = md.renderer.render(tokens, md.options, env)
  const headings = tokens.flatMap((token, i) => token.type === 'heading_open' && token.tag === 'h2' ? [{ id: token.attrGet('id'), text: tokens[i + 1].content }] : [])
  const toc = headings.map(h => '<a href="#' + escape(h.id) + '">' + escape(h.text) + '</a>').join('')
  const sidebar = docs.map(d => '<a href="' + url('docs/' + d.slug + '.html') + '"' + (d === doc ? ' aria-current="page"' : '') + '>' + escape(d.title) + '</a>').join('')
  save('docs/' + doc.slug + '.html', doc.title, '<div class="docs-layout"><aside class="docs-sidebar" aria-label="文档目录"><a class="eyebrow" href="' + url('docs/index.html') + '">文档目录</a>' + sidebar + '</aside><article class="prose"><p class="source-note">来源：<a href="' + sourceURL(doc.source) + '">' + escape(doc.source) + '</a> · 源码 ' + short + '</p>' + html + '</article><aside class="toc" aria-label="本页标题"><strong>本页内容</strong>' + toc + '</aside></div>')
}
save('download.html', '下载', '<section class="page-heading"><p class="eyebrow">DOWNLOAD</p><h1>下载 ' + project.title + '</h1><p class="lead">' + project.downloadDescription + '</p></section><section class="download-layout"><div class="download-card"><span class="eyebrow">VERSIONED SOURCE</span><h2>源码 ZIP</h2><p>提交快照 <strong>' + short + '</strong> · ' + (bytes.length / 1024).toFixed(0) + ' KB</p>' + button('一键下载源码', url('downloads/' + archive), true, true) +
  '<dl><dt>完整提交</dt><dd><a href="' + project.repository + '/commit/' + revision + '"><code>' + revision + '</code></a></dd><dt>SHA-256</dt><dd><code>' + hash + '</code></dd><dt>许可</dt><dd>' + project.license + '</dd></dl><a href="' + url('downloads/' + archive + '.sha256') + '" download>下载校验文件</a></div><div class="download-notes"><h2>下载之后</h2><p>' + project.requirements + '</p><p>这是源码快照，不是免安装应用。解压后按快速开始配置环境。</p>' + button('查看安装步骤', url('getting-started.html')) + (project.installCommand ? code(sourceCommand, '已有 Python 与 pipx 时') : '') +
  '<h3>正式版本</h3><p>本站当前提供提交快照。已发布版本与附件以 GitHub Releases 为准。</p><a href="' + releaseURL + '">查看 GitHub Releases</a></div></section>')
const changelog = tracked.has('CHANGELOG.md') ? md.render(git('show', revision + ':CHANGELOG.md'), { source: 'CHANGELOG.md' }) : '<p>目前没有版本日志。</p>'
save('changelog.html', '更新记录', '<section class="page-heading"><p class="eyebrow">CHANGELOG</p><h1>更新记录</h1><p class="lead">以下来自源码 ' + short + ' 的 CHANGELOG；未发布内容会保留原有标记。</p></section><div class="article-wrap"><article class="prose">' + changelog + '</article></div>')
save('404.html', '页面未找到', '<section class="page-heading"><p class="eyebrow">404</p><h1>页面未找到</h1><p class="lead">请返回首页，或从文档目录继续阅读。</p>' + button('返回首页', url('index.html'), true) + '</section>')
console.log(JSON.stringify({ project: project.title, output: out, revision, archive, sha256: hash, documents: docs.length, base }))
