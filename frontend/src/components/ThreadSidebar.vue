<template>
  <aside class="w-72 border-r border-slate-200/80 dark:border-slate-800/80 bg-white/60 dark:bg-slate-950/60 flex flex-col h-[calc(100vh-61px)] flex-shrink-0 transition-colors duration-200">
    <!-- Header -->
    <div class="p-4 border-b border-slate-200/80 dark:border-slate-800/80 flex items-center justify-between">
      <div class="flex items-center space-x-2">
        <Layers class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
        <span class="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">研究任务列表</span>
      </div>
      <button
        @click="store.fetchThreads"
        class="p-1.5 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        title="刷新列表"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" />
      </button>
    </div>

    <!-- Thread List -->
    <div class="flex-1 overflow-y-auto p-3 space-y-2">
      <div v-if="!store.threads.length" class="text-center py-10 px-4">
        <FileText class="w-8 h-8 mx-auto text-slate-400 dark:text-slate-600 mb-2 stroke-[1.5]" />
        <p class="text-xs text-slate-500 dark:text-slate-400">暂无历史研究任务</p>
        <p class="text-[11px] text-slate-400 dark:text-slate-600 mt-1">点击右上角“发起新研究”开始</p>
      </div>

      <div
        v-for="item in store.threads"
        :key="item.thread_id"
        @click="handleSelect(item.thread_id)"
        :class="[
          'group relative p-3 rounded-xl transition-all duration-200 cursor-pointer border text-left',
          store.currentThreadId === item.thread_id
            ? 'bg-indigo-50/70 dark:bg-slate-900 border-indigo-500/50 shadow-md shadow-indigo-500/10'
            : 'bg-white/80 dark:bg-slate-900/40 hover:bg-slate-50 dark:hover:bg-slate-900/80 border-slate-200/80 dark:border-slate-800/60 hover:border-slate-300 dark:hover:border-slate-700'
        ]"
      >
        <!-- Top Row: Topic -->
        <div class="flex items-start justify-between gap-2 mb-1.5">
          <h4
            class="text-xs font-medium text-slate-800 dark:text-slate-200 line-clamp-2 leading-relaxed transition-colors"
            :class="{ 'text-indigo-600 dark:text-indigo-300 font-semibold': store.currentThreadId === item.thread_id }"
          >
            {{ item.topic }}
          </h4>
        </div>

        <!-- Meta info & Status tag -->
        <div class="flex items-center justify-between text-[11px] mt-2">
          <!-- Status Badge -->
          <span
            v-if="item.status === 'completed'"
            class="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/80"
          >
            <CheckCircle2 class="w-3 h-3" />
            <span>已完成</span>
          </span>
          <span
            v-else-if="item.status === 'waiting_approval'"
            class="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] bg-amber-50 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/80 animate-pulse"
          >
            <Clock class="w-3 h-3" />
            <span>待审批</span>
          </span>
          <span
            v-else
            class="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/80"
          >
            <Loader2 class="w-3 h-3 animate-spin" />
            <span>运行中</span>
          </span>

          <!-- Fork Branch tag if exists -->
          <span
            v-if="item.parent_thread_id"
            class="text-[10px] text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/60 px-1 py-0.5 rounded border border-purple-200 dark:border-purple-800/60"
            title="时间旅行分支"
          >
            🌿 分支
          </span>

          <!-- Cost or Score -->
          <div class="text-[10px] text-slate-500 dark:text-slate-400 font-mono">
            <span v-if="item.review_score !== null && item.review_score !== undefined" class="text-amber-600 dark:text-amber-400 font-medium">
              {{ item.review_score }}分
            </span>
            <span v-else-if="item.usage?.cost_usd" class="text-slate-500 dark:text-slate-400">
              ${{ item.usage.cost_usd.toFixed(4) }}
            </span>
          </div>
        </div>

        <!-- Thread ID Footer -->
        <div class="mt-2 pt-1.5 border-t border-slate-100 dark:border-slate-800/40 flex items-center justify-between text-[10px] text-slate-400 dark:text-slate-500 font-mono">
          <span class="truncate max-w-[130px]">{{ item.thread_id }}</span>
          <span v-if="item.plan?.length">{{ item.plan.length }} 个任务</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import {
  Layers,
  RefreshCw,
  FileText,
  CheckCircle2,
  Clock,
  Loader2,
} from 'lucide-vue-next'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()
const loading = ref(false)

const handleSelect = async (threadId) => {
  if (store.currentThreadId === threadId) return
  await store.selectThread(threadId)
}
</script>
