import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: localStorage.getItem('theme_mode') || 'system', // 'light' | 'dark' | 'system'
    systemIsDark: window.matchMedia('(prefers-color-scheme: dark)').matches,
  }),

  getters: {
    isDark: (state) => {
      if (state.mode === 'system') {
        return state.systemIsDark
      }
      return state.mode === 'dark'
    },
  },

  actions: {
    initTheme() {
      // Listen to system preference changes
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      const handler = (e) => {
        this.systemIsDark = e.matches
        this.applyTheme()
      }
      if (mediaQuery.addEventListener) {
        mediaQuery.addEventListener('change', handler)
      } else {
        mediaQuery.addListener(handler)
      }
      this.applyTheme()
    },

    setTheme(mode) {
      if (!['light', 'dark', 'system'].includes(mode)) return
      this.mode = mode
      localStorage.setItem('theme_mode', mode)
      this.applyTheme()
    },

    applyTheme() {
      const isDark = this.isDark
      if (isDark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },
  },
})
