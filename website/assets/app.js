const menu = document.querySelector('.menu-toggle')
const nav = document.querySelector('.site-nav')
menu?.addEventListener('click', () => {
  const expanded = menu.getAttribute('aria-expanded') !== 'true'
  menu.setAttribute('aria-expanded', String(expanded))
  nav.classList.toggle('is-open', expanded)
})
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && menu?.getAttribute('aria-expanded') === 'true') {
    menu.setAttribute('aria-expanded', 'false')
    nav.classList.remove('is-open')
    menu.focus()
  }
})
document.querySelectorAll('pre').forEach(pre => {
  const code = pre.querySelector('code')
  if (!code) return
  const button = document.createElement('button')
  button.className = 'copy-button'
  button.type = 'button'
  button.textContent = '复制'
  button.setAttribute('aria-label', '复制此代码块')
  button.addEventListener('click', async () => {
    const status = document.querySelector('.copy-status')
    try {
      await navigator.clipboard.writeText(code.textContent)
      button.textContent = '已复制'
      if (status) status.textContent = '代码已复制'
    } catch {
      button.textContent = '请手动复制'
      if (status) status.textContent = '复制失败，请选择代码后手动复制'
    }
    window.setTimeout(() => { button.textContent = '复制' }, 2500)
  })
  pre.append(button)
})

