<template>
  <div class="space-y-4">
    <!-- Stats Metrics Grid -->
    <div class="glass-card rounded-2xl p-4 border border-slate-200/90 dark:border-slate-800/80 transition-colors">
      <div class="flex items-center space-x-2 mb-3">
        <Activity class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
        <h3 class="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">用量与预算仪表盘</h3>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <!-- Cost USD -->
        <div class="bg-slate-50 dark:bg-slate-900/90 border border-slate-200/80 dark:border-slate-800/80 rounded-xl p-3">
          <div class="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-1">
            <span>预估费用</span>
            <DollarSign class="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div class="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {{ store.formattedCost }}
          </div>
          <div class="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
            上限: ${{ store.config?.max_cost_usd || 1.0 }}
          </div>
        </div>

        <!-- Total Tokens -->
        <div class="bg-slate-50 dark:bg-slate-900/90 border border-slate-200/80 dark:border-slate-800/80 rounded-xl p-3">
          <div class="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-1">
            <span>估算 Tokens</span>
            <Cpu class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div class="text-base font-bold font-mono text-indigo-600 dark:text-indigo-300">
            {{ store.totalTokensFormatted }}
          </div>
          <div class="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
            上限: {{ (store.config?.max_total_tokens || 80000).toLocaleString() }}
          </div>
        </div>

        <!-- LLM Calls -->
        <div class="bg-slate-50 dark:bg-slate-900/90 border border-slate-200/80 dark:border-slate-800/80 rounded-xl p-3">
          <div class="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-1">
            <span>LLM 调用数</span>
            <Brain class="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
          </div>
          <div class="text-base font-bold font-mono text-slate-800 dark:text-slate-100">
            {{ store.usage?.llm_calls || 0 }}
          </div>
          <div class="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
            上限: {{ store.config?.llm_max_calls || 30 }} 次
          </div>
        </div>

        <!-- Search Calls -->
        <div class="bg-slate-50 dark:bg-slate-900/90 border border-slate-200/80 dark:border-slate-800/80 rounded-xl p-3">
          <div class="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-1">
            <span>搜索调用数</span>
            <Search class="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
          </div>
          <div class="text-base font-bold font-mono text-sky-600 dark:text-sky-300">
            {{ store.usage?.search_calls || 0 }}
          </div>
          <div class="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
            上限轮次: {{ store.config?.search_max_rounds || 3 }} 轮
          </div>
        </div>
      </div>

      <!-- Budget Alert if exhausted -->
      <div
        v-if="store.budgetExhausted"
        class="mt-3 p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-500/40 text-xs text-rose-700 dark:text-rose-300 flex items-center space-x-2"
      >
        <AlertTriangle class="w-4 h-4 text-rose-600 dark:text-rose-400 flex-shrink-0" />
        <span>{{ store.terminationReason || '预算或调用上限已触发，工作流安全停止。' }}</span>
      </div>
    </div>

    <!-- Live Execution Terminal Logs -->
    <div class="glass-card rounded-2xl p-4 border border-slate-200/90 dark:border-slate-800/80 transition-colors">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center space-x-2">
          <Terminal class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          <h3 class="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">实时执行日志 (Live Logs)</h3>
        </div>
        <span v-if="store.isStreaming" class="inline-flex items-center space-x-1 text-[10px] text-emerald-600 dark:text-emerald-400">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
          <span>连接中</span>
        </span>
      </div>

      <div class="bg-slate-900 dark:bg-slate-950/90 rounded-xl p-3 font-mono text-[11px] h-48 overflow-y-auto space-y-1.5 border border-slate-800 dark:border-slate-900 text-slate-200">
        <div v-if="!store.liveLogs.length" class="text-slate-500 text-center py-6">
          暂无实时日志输出
        </div>

        <div
          v-for="log in store.liveLogs"
          :key="log.id"
          class="flex items-start space-x-2 leading-relaxed"
        >
          <span class="text-slate-500 select-none flex-shrink-0">[{{ log.time }}]</span>
          <span
            :class="[
              log.type === 'success' ? 'text-emerald-400' : '',
              log.type === 'warning' ? 'text-amber-400' : '',
              log.type === 'error' ? 'text-rose-400' : '',
              log.type === 'info' ? 'text-slate-200' : '',
            ]"
          >
            {{ log.text }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  Activity,
  DollarSign,
  Cpu,
  Brain,
  Search,
  AlertTriangle,
  Terminal,
} from 'lucide-vue-next'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()
</script>
