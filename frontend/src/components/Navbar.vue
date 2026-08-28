<template>
  <header class="glass-panel sticky top-0 z-30 px-6 py-3.5 flex items-center justify-between border-b border-slate-200/80 dark:border-slate-800/80 transition-colors duration-200">
    <!-- Left: Brand Logo & Title -->
    <div class="flex items-center space-x-3.5">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/25 ring-1 ring-white/20">
        <Sparkles class="w-5 h-5 text-white animate-pulse-subtle" />
      </div>
      <div>
        <div class="flex items-center space-x-2">
          <h1 class="text-lg font-bold font-heading bg-clip-text text-transparent bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-600 dark:from-white dark:via-slate-100 dark:to-indigo-200">
            Mini Research Agent
          </h1>
          <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            v1.2 Stage 12
          </span>
        </div>
        <p class="text-xs text-slate-500 dark:text-slate-400">
          基于 LangGraph 的多智能体深度研报与时间旅行系统
        </p>
      </div>
    </div>

    <!-- Center: Runtime Model Badge -->
    <div v-if="store.config" class="hidden md:flex items-center space-x-2 bg-slate-100/90 dark:bg-slate-900/90 px-3.5 py-1.5 rounded-full border border-slate-200 dark:border-slate-800 text-xs transition-colors">
      <span class="flex h-2 w-2 relative">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
        <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
      </span>
      <span class="text-slate-500 dark:text-slate-400">引擎:</span>
      <span class="font-medium text-slate-800 dark:text-slate-200 uppercase">{{ store.config.provider }}</span>
      <span class="text-slate-300 dark:text-slate-600">|</span>
      <span class="text-slate-500 dark:text-slate-400">模型:</span>
      <span class="font-mono text-indigo-600 dark:text-indigo-300">{{ store.config.model }}</span>
    </div>

    <!-- Right: Theme Switcher & Actions -->
    <div class="flex items-center space-x-3">
      <!-- Theme Switcher Segmented Control -->
      <div class="flex items-center p-1 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 transition-colors">
        <button
          @click="themeStore.setTheme('light')"
          :class="[
            'p-1.5 rounded-lg text-xs transition-all cursor-pointer flex items-center justify-center',
            themeStore.mode === 'light'
              ? 'bg-white dark:bg-slate-800 text-amber-500 shadow-sm'
              : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
          ]"
          title="浅色模式"
        >
          <Sun class="w-3.5 h-3.5" />
        </button>

        <button
          @click="themeStore.setTheme('dark')"
          :class="[
            'p-1.5 rounded-lg text-xs transition-all cursor-pointer flex items-center justify-center',
            themeStore.mode === 'dark'
              ? 'bg-white dark:bg-slate-800 text-indigo-400 shadow-sm'
              : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
          ]"
          title="深色模式"
        >
          <Moon class="w-3.5 h-3.5" />
        </button>

        <button
          @click="themeStore.setTheme('system')"
          :class="[
            'p-1.5 rounded-lg text-xs transition-all cursor-pointer flex items-center justify-center',
            themeStore.mode === 'system'
              ? 'bg-white dark:bg-slate-800 text-indigo-500 dark:text-indigo-400 shadow-sm'
              : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
          ]"
          title="跟随系统"
        >
          <Laptop class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Time Travel Button -->
      <button
        v-if="store.hasActiveThread"
        @click="store.showTimeTravelDrawer = true"
        class="inline-flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-800/80 dark:hover:bg-slate-700/80 text-purple-600 dark:text-purple-300 border border-purple-300/40 dark:border-purple-500/30 hover:border-purple-500/50 transition-all duration-200 cursor-pointer shadow-sm hover:shadow-purple-500/10"
      >
        <History class="w-4 h-4 text-purple-500 dark:text-purple-400" />
        <span>时间旅行 & 审查</span>
        <span v-if="store.checkpointHistory.length" class="px-1.5 py-0.2 bg-purple-100 dark:bg-purple-950/80 text-purple-700 dark:text-purple-300 rounded text-[10px] border border-purple-200 dark:border-purple-800">
          {{ store.checkpointHistory.length }}
        </span>
      </button>

      <!-- New Research Button -->
      <button
        @click="store.showNewResearchModal = true"
        class="inline-flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white shadow-md shadow-indigo-600/30 transition-all duration-200 cursor-pointer hover:scale-[1.02] active:scale-[0.98]"
      >
        <PlusCircle class="w-4 h-4" />
        <span>发起新研究</span>
      </button>
    </div>
  </header>
</template>

<script setup>
import { Sparkles, History, PlusCircle, Sun, Moon, Laptop } from 'lucide-vue-next'
import { useResearchStore } from '../stores/research'
import { useThemeStore } from '../stores/theme'

const store = useResearchStore()
const themeStore = useThemeStore()
</script>
