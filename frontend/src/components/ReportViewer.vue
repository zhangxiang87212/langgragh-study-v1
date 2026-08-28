<template>
  <div class="glass-card rounded-2xl p-6 border border-slate-200/90 dark:border-slate-800/80 transition-colors">
    <!-- Top Bar: Report Title & Actions -->
    <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-200/80 dark:border-slate-800/80">
      <div class="flex items-center space-x-3">
        <div class="w-9 h-9 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
          <BookOpen class="w-4 h-4" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center space-x-2">
            <span>深度研究分析报告</span>
            <span v-if="store.isStreaming && store.activeNode === 'writer'" class="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30">
              <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping"></span>
              <span>实时生成中...</span>
            </span>
          </h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            由 Writer 智能体整合多方证据生成，经 Reviewer 结构化质量审核
          </p>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center space-x-2">
        <button
          v-if="store.draft"
          @click="handleCopy"
          class="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-900 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 transition-colors cursor-pointer"
        >
          <Copy class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
          <span>{{ copied ? '已复制' : '复制 Markdown' }}</span>
        </button>

        <button
          v-if="store.draft"
          @click="handleDownload"
          class="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-900 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 transition-colors cursor-pointer"
        >
          <Download class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
          <span>导出文件</span>
        </button>
      </div>
    </div>

    <!-- Reviewer Feedback Banner (if available) -->
    <div
      v-if="store.reviewScore !== null && store.reviewScore !== undefined"
      :class="[
        'rounded-xl p-3.5 mb-5 border flex items-center justify-between transition-all duration-300',
        store.reviewScore >= 80 ? 'bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-300 dark:border-emerald-500/30' : 'bg-amber-50/50 dark:bg-amber-950/20 border-amber-300 dark:border-amber-500/30'
      ]"
    >
      <div class="flex items-center space-x-3">
        <div
          :class="[
            'w-10 h-10 rounded-xl flex items-center justify-center font-bold font-mono text-sm border',
            store.reviewScore >= 80 ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-500/40' : 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-500/40'
          ]"
        >
          {{ store.reviewScore }}
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <span class="text-xs font-semibold text-slate-800 dark:text-slate-200">Reviewer 质量审核评级</span>
            <span
              :class="[
                'px-2 py-0.5 rounded text-[10px] font-medium border',
                store.reviewScore >= 80 ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800' : 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800'
              ]"
            >
              {{ store.reviewScore >= 80 ? '审核通过 (≥80)' : '需进一步修订' }}
            </span>
          </div>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {{ store.reviewComment || '研报结构完整，论点清晰，引用真实规范。' }}
          </p>
        </div>
      </div>

      <div class="text-right text-xs text-slate-500 dark:text-slate-400">
        <div>修订轮次: <span class="font-mono text-slate-700 dark:text-slate-300">{{ store.revisionCount }} 轮</span></div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!store.draft" class="text-center py-16 px-4">
      <div class="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 mx-auto flex items-center justify-center text-slate-400 dark:text-slate-600 mb-3">
        <FileText class="w-7 h-7 stroke-[1.5]" />
      </div>
      <h4 class="text-xs font-medium text-slate-600 dark:text-slate-400">研报尚未生成</h4>
      <p class="text-[11px] text-slate-400 dark:text-slate-600 mt-1 max-w-sm mx-auto">
        当 Graph 执行完并行检索与质量评估后，Writer 将在此处实时流式撰写完整报告。
      </p>
    </div>

    <!-- Rendered Markdown Body with Typing Cursor -->
    <div v-else class="relative">
      <div class="markdown-body" v-html="renderedMarkdown"></div>
      
      <!-- Live streaming typing cursor -->
      <span
        v-if="store.isStreaming && store.activeNode === 'writer'"
        class="inline-block w-2 h-4 ml-1 bg-indigo-500 animate-pulse align-middle"
      ></span>
    </div>

    <!-- Sources & Evidence Footer -->
    <div v-if="store.sources && store.sources.length" class="mt-8 pt-4 border-t border-slate-200/80 dark:border-slate-800/80">
      <h4 class="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
        <Link2 class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
        <span>参考文献与溯源 URL ({{ store.sources.length }})</span>
      </h4>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
        <a
          v-for="(source, sIdx) in store.sources"
          :key="sIdx"
          :href="source"
          target="_blank"
          rel="noopener noreferrer"
          class="flex items-center space-x-1.5 p-2 rounded-lg bg-slate-50 dark:bg-slate-900/60 hover:bg-slate-100 dark:hover:bg-slate-900 border border-slate-200 dark:border-slate-800/80 hover:border-indigo-400 text-[11px] text-indigo-600 dark:text-indigo-300 hover:underline transition-colors"
        >
          <span class="text-slate-400 dark:text-slate-500 font-mono text-[10px] w-4">[{{ sIdx + 1 }}]</span>
          <span class="truncate flex-1">{{ source }}</span>
          <ExternalLink class="w-3 h-3 text-slate-400 dark:text-slate-500 flex-shrink-0" />
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { BookOpen, Copy, Download, FileText, Link2, ExternalLink } from 'lucide-vue-next'
import { message } from 'ant-design-vue'
import { marked } from 'marked'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()
const copied = ref(false)

const renderedMarkdown = computed(() => {
  if (!store.draft) return ''
  try {
    return marked.parse(store.draft)
  } catch (err) {
    return store.draft
  }
})

const handleCopy = async () => {
  if (!store.draft) return
  try {
    await navigator.clipboard.writeText(store.draft)
    copied.value = true
    message.success('研报已复制到剪贴板')
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    message.error('复制失败')
  }
}

const handleDownload = () => {
  if (!store.draft) return
  const blob = new Blob([store.draft], { type: 'text/markdown;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${store.topic || 'research-report'}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>
