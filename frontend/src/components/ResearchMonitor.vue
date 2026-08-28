<template>
  <div class="space-y-4">
    <!-- Evaluator Score Card (if evaluated) -->
    <div
      v-if="store.researchScore !== null && store.researchScore !== undefined"
      :class="[
        'glass-card rounded-2xl p-4 border transition-all duration-300',
        store.researchScore >= 80 ? 'border-emerald-500/30 bg-emerald-50/40 dark:bg-emerald-950/10' : 'border-amber-500/30 bg-amber-50/40 dark:bg-amber-950/10'
      ]"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div
            :class="[
              'w-10 h-10 rounded-xl flex items-center justify-center font-bold font-mono text-sm border',
              store.researchScore >= 80 ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/40' : 'bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/40'
            ]"
          >
            {{ store.researchScore }}
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h4 class="text-xs font-semibold text-slate-800 dark:text-slate-200">Research Evaluator 资料评估</h4>
              <span
                :class="[
                  'px-2 py-0.5 rounded text-[10px] font-medium border',
                  store.researchScore >= 80 ? 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800' : 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800'
                ]"
              >
                {{ store.researchScore >= 80 ? '评估达标 (≥80)' : '需补充检索' }}
              </span>
            </div>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {{ store.researchComment || '综合任务覆盖度、来源权威性、时效性与证据充分度。' }}
            </p>
          </div>
        </div>

        <div class="text-right text-xs text-slate-500 dark:text-slate-400">
          <div>来源链接: <span class="font-mono text-indigo-600 dark:text-indigo-400 font-semibold">{{ store.sources.length }}</span> 篇</div>
          <div>迭代轮次: <span class="font-mono text-slate-700 dark:text-slate-300">Round {{ store.researchResults.length ? (store.researchResults[0].research_iteration || 1) : 1 }}</span></div>
        </div>
      </div>
    </div>

    <!-- Parallel Research Workers Grid -->
    <div class="glass-card rounded-2xl p-4 border border-slate-200/90 dark:border-slate-800/80 transition-colors">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center space-x-2">
          <Globe class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          <h3 class="text-xs font-semibold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
            并行 Research Workers ({{ store.researchResults.length }} / {{ store.plan.length || 0 }})
          </h3>
        </div>
        <span v-if="store.isStreaming && store.activeNode === 'research_worker'" class="inline-flex items-center space-x-1 text-[11px] text-indigo-600 dark:text-indigo-400">
          <Loader2 class="w-3.5 h-3.5 animate-spin" />
          <span>正在联网检索中...</span>
        </span>
      </div>

      <div v-if="!store.researchResults.length && !store.plan.length" class="text-center py-8 text-xs text-slate-400 dark:text-slate-500">
        暂无检索任务数据
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div
          v-for="(result, idx) in displayWorkerCards"
          :key="idx"
          class="bg-slate-50/80 dark:bg-slate-900/80 border border-slate-200/80 dark:border-slate-800/90 rounded-xl p-3 flex flex-col justify-between hover:border-indigo-300 dark:hover:border-slate-700 transition-colors"
        >
          <div>
            <!-- Worker Header -->
            <div class="flex items-center justify-between mb-2">
              <span class="px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/50 text-[10px] font-mono font-medium">
                Worker #{{ idx + 1 }}
              </span>
              <span v-if="result.completed" class="inline-flex items-center space-x-1 text-[10px] text-emerald-600 dark:text-emerald-400">
                <CheckCircle class="w-3 h-3" />
                <span>已完成</span>
              </span>
              <span v-else class="inline-flex items-center space-x-1 text-[10px] text-slate-400 dark:text-slate-500">
                <Clock class="w-3 h-3" />
                <span>等待中</span>
              </span>
            </div>

            <!-- Task Title -->
            <h5 class="text-xs font-medium text-slate-800 dark:text-slate-200 mb-2 line-clamp-2">
              {{ result.task }}
            </h5>

            <!-- Extracted summary / snippet -->
            <p v-if="result.content" class="text-[11px] text-slate-600 dark:text-slate-400 line-clamp-3 leading-relaxed mb-3 bg-white dark:bg-slate-950/60 p-2 rounded border border-slate-200/60 dark:border-slate-900">
              {{ result.content }}
            </p>
          </div>

          <!-- Sources list -->
          <div v-if="result.sources && result.sources.length" class="mt-2 pt-2 border-t border-slate-200/60 dark:border-slate-800/60">
            <span class="text-[10px] text-slate-400 dark:text-slate-500 block mb-1">参考来源 ({{ result.sources.length }}):</span>
            <div class="space-y-1">
              <a
                v-for="(url, sIdx) in result.sources.slice(0, 2)"
                :key="sIdx"
                :href="url"
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center space-x-1 text-[10px] text-indigo-600 dark:text-indigo-400 hover:underline truncate max-w-full"
              >
                <ExternalLink class="w-2.5 h-2.5 flex-shrink-0" />
                <span class="truncate">{{ url }}</span>
              </a>
              <span v-if="result.sources.length > 2" class="text-[10px] text-slate-400 dark:text-slate-500">
                + 其他 {{ result.sources.length - 2 }} 个链接
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Globe, CheckCircle, Clock, ExternalLink, Loader2 } from 'lucide-vue-next'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()

const displayWorkerCards = computed(() => {
  if (store.researchResults && store.researchResults.length) {
    return store.researchResults.map(r => ({
      ...r,
      completed: true,
    }))
  }
  if (store.plan && store.plan.length) {
    return store.plan.map((p, idx) => ({
      task_index: idx,
      task: p,
      completed: false,
      sources: [],
    }))
  }
  return []
})
</script>
