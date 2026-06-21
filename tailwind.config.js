/** @type {import('tailwindcss').Config} */
// 由原 base.html 内联 tailwind.config 1:1 迁移而来，配合本地构建替代 Play CDN。
module.exports = {
  darkMode: 'class',
  // content 决定哪些 class 会被保留：模板 + JS（main.js / 内联脚本里动态切换的 class 也要扫到）
  content: [
    './app/templates/**/*.html',
    './app/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#0e5e6e',
        'primary-dark': '#0a4a57',
        'primary-light': '#e8f4f6',
        'on-primary': '#ffffff',
        'surface': '#f5f7fa',
        'on-surface': '#2d3748',
        'on-surface-variant': '#4a5568',
        'outline-variant': '#d1d9e0',
        'secondary': '#2c7a50',
        'secondary-light': '#edf7f1',
        'accent': '#c8a45c',
        'background': '#f5f7fa',
      },
      fontFamily: {
        'serif-cn': ["'Noto Serif SC'", "'STZhongsong'", 'serif'],
        'sans-cn': ["'Noto Sans SC'", "'PingFang SC'", 'sans-serif'],
        'mono': ["'JetBrains Mono'", 'monospace'],
      },
      maxWidth: {
        'container': '1440px',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
