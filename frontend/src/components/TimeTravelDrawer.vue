<template>
  <a-drawer
    :open="store.showTimeTravelDrawer"
    :title="null"
    placement="right"
    width="760px"
    @close="store.showTimeTravelDrawer = false"
    class="custom-time-travel-drawer"
  >
    <div class="flex flex-col h-full text-slate-800 dark:text-slate-100">
      <!-- Drawer Header -->
      <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-200 dark:border-slate-800">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-500/20 border border-purple-200 dark:border-purple-500/30 flex items-center justify-center text-purple-600 dark:text-purple-400">
            <History class="w-5 h-5" />
          </div>
          <div>
            <h3 class="text-base font-bold text-slate-900 dark:text-slate-100">
              Checkpoint 时间旅行与人工修正
            </h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              审查历史快照状态，从任意历史点创建独立线程分支修正执行
            </p>
          </div>
        </div>

        <button
          @click="store.showTimeTravelDrawer = false"
          class="p-2 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Tab Navigation -->
      <div class="flex items-center space-x-2 mb-4 bg-slate-100 dark:bg-slate-900/80 p-1 rounded-xl border border-slate-200 dark:border-slate-800">
        <button
          @click="activeTab = 'timeline'"
          :class="[
            'flex-1 py-1.5 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer flex items-center justify-center space-x-1.5',
            activeTab === 'timeline' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
          ]"
        >
          <GitCommit class="w-3.5 h-3.5" />
          <span>快照时间线 ({{ store.checkpointHistory.length }})</span>
        </button>

        <button
          @click="activeTab = 'inspect'"
          :class="[
            'flex-1 py-1.5 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer flex items-center justify-center space-x-1.5',
            activeTab === 'inspect' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
          ]"
        >
          <SearchCode class="w-3.5 h-3.5" />
          <span>资料审查详情</span>
        </button>

        <button
          @click="activeTab = 'fork'"
          :class="[
            'flex-1 py-1.5 px-3 rounded-lg text-xs font-medium transition-all cursor-pointer flex items-center justify-center space-x-1.5',
            activeTab === 'fork' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
          ]"
        >
          <GitFork class="w-3.5 h-3.5" />
          <span>创建修正分支 (Fork)</span>
        </button>
      </div>

      <!-- Content Area -->
      <div class="flex-1 overflow-y-auto pr-1">
        <!-- TAB 1: Checkpoint Timeline -->
        <div v-if="activeTab === 'timeline'" class="space-y-3">
          <div v-if="!store.checkpointHistory.length" class="text-center py-12 text-xs text-slate-400 dark:text-slate-500">
            暂无历史快照记录
          </div>

          <div
            v-for="(cp, idx) in store.checkpointHistory"
            :key="cp.checkpoint_id"
            :class="[
              'p-3.5 rounded-xl border transition-all cursor-pointer',
              selectedCpId === cp.checkpoint_id
                ? 'bg-purple-50/60 dark:bg-slate-900 border-purple-500/60 shadow-md shadow-purple-500/10'
                : 'bg-white dark:bg-slate-900/60 hover:bg-slate-50 dark:hover:bg-slate-900 border-slate-200 dark:border-slate-800'
            ]"
            @click="handleSelectCheckpoint(cp.checkpoint_id)"
          >
            <div class="flex items-center justify-between mb-1.5">
              <div class="flex items-center space-x-2">
                <span class="w-5 h-5 rounded-md bg-purple-100 dark:bg-purple-950/80 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/60 flex items-center justify-center text-[10px] font-mono font-bold">
                  {{ idx + 1 }}
                </span>
                <span class="text-xs font-semibold text-slate-800 dark:text-slate-200">
                  Step {{ cp.step !== undefined ? cp.step : 'N/A' }}: {{ (cp.next_nodes && cp.next_nodes.length) ? cp.next_nodes.join(', ') : 'END' }}
                </span>
              </div>

              <span class="text-[10px] font-mono text-slate-400 dark:text-slate-500 truncate max-w-[120px]">
                {{ cp.checkpoint_id.slice(0, 12) }}...
              </span>
            </div>

            <div class="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mt-2">
              <div>
                <span>计划任务: {{ cp.plan_count }} 项</span>
                <span v-if="cp.research_score !== null && cp.research_score !== undefined" class="ml-2 text-indigo-600 dark:text-indigo-300">
                  评估: {{ cp.research_score }}分
                </span>
              </div>

              <div class="flex items-center space-x-2">
                <button
                  @click.stop="quickFork(cp.checkpoint_id)"
                  class="px-2 py-0.5 rounded text-[10px] bg-purple-100 dark:bg-purple-950/80 hover:bg-purple-200 dark:hover:bg-purple-900 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 transition-colors"
                >
                  以此为起点 Fork
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 2: Inspection Document -->
        <div v-if="activeTab === 'inspect'" class="space-y-4">
          <div class="flex items-center justify-between bg-slate-100 dark:bg-slate-900/80 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs">
            <span class="text-slate-500 dark:text-slate-400">正在审查快照：</span>
            <span class="font-mono text-purple-600 dark:text-purple-300">{{ selectedCpId ? selectedCpId.slice(0, 16) + '...' : '最新快照' }}</span>
          </div>

          <div v-if="loadingInspect" class="text-center py-12 text-xs text-slate-400">
            <Loader2 class="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500" />
            <span>加载快照审查数据中...</span>
          </div>

          <div v-else-if="inspectResult" class="bg-white dark:bg-slate-950/80 rounded-xl p-4 border border-slate-200 dark:border-slate-800/80">
            <div class="markdown-body" v-html="renderedInspectMarkdown"></div>
          </div>

          <div v-else class="text-center py-12 text-xs text-slate-400 dark:text-slate-500">
            请从时间线中选择快照查看审查
          </div>
        </div>

        <!-- TAB 3: Fork Branch Form -->
        <div v-if="activeTab === 'fork'" class="space-y-4">
          <div class="bg-purple-50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-500/30 rounded-xl p-3 text-xs text-purple-800 dark:text-purple-200 flex items-start space-x-2">
            <Info class="w-4 h-4 text-purple-600 dark:text-purple-400 flex-shrink-0 mt-0.5" />
            <div>
              <span>从历史 Checkpoint 创建独立线程分支。原线程不会被修改，修正点之前已完成的昂贵节点不会重跑。</span>
            </div>
          </div>

          <!-- Base Checkpoint Selection -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">分叉起点 Checkpoint ID</label>
            <input
              v-model="forkForm.checkpointId"
              type="text"
              placeholder="输入或从时间线中点击选择 Checkpoint ID"
              class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none focus:border-purple-500"
            />
          </div>

          <!-- Plan Revision -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              修改/替换研究计划 (可选，用分号分隔任务)
            </label>
            <textarea
              v-model="forkForm.revisedPlanStr"
              rows="2"
              placeholder="例如：任务1：调研教育大模型进展; 任务2：分析商业化落地痛点"
              class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:border-purple-500 resize-none"
            ></textarea>
          </div>

          <!-- Remove Source URLs -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              删除错误/不可信来源 URL (可选，每行一个或逗号分隔)
            </label>
            <textarea
              v-model="forkForm.removeSourcesStr"
              rows="2"
              placeholder="https://example.com/unreliable-source"
              class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none focus:border-purple-500 resize-none"
            ></textarea>
          </div>

          <!-- Remove Text Fragments -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              从研究资料中剔除错误文字片段 (可选，每行一个)
            </label>
            <textarea
              v-model="forkForm.removeTextsStr"
              rows="2"
              placeholder="输入需要从前序汇总资料中剔除的错误内容..."
              class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:border-purple-500 resize-none"
            ></textarea>
          </div>

          <!-- Manual Evidence Injection -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              补充人工可信证据 (可选，每行一条)
            </label>
            <textarea
              v-model="forkForm.manualEvidenceStr"
              rows="2"
              placeholder="输入权威的人工事实补充，将直接注入资料库供后续节点使用..."
              class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:border-purple-500 resize-none"
            ></textarea>
          </div>

          <!-- Fork Submit Button -->
          <div class="pt-2">
            <button
              @click="submitFork"
              class="w-full py-2.5 rounded-xl font-medium text-xs bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-md shadow-purple-600/30 transition-all cursor-pointer flex items-center justify-center space-x-2"
            >
              <GitFork class="w-4 h-4" />
              <span>立即创建分支并执行修正</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import {
  History,
  X,
  GitCommit,
  SearchCode,
  GitFork,
  Loader2,
  Info,
} from 'lucide-vue-next'
import { message } from 'ant-design-vue'
import { marked } from 'marked'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()
const activeTab = ref('timeline')
const selectedCpId = ref(null)
const inspectResult = ref(null)
const loadingInspect = ref(false)

const forkForm = reactive({
  checkpointId: '',
  revisedPlanStr: '',
  removeSourcesStr: '',
  removeTextsStr: '',
  manualEvidenceStr: '',
})

watch(
  () => store.checkpointHistory,
  (list) => {
    if (list && list.length && !selectedCpId.value) {
      selectedCpId.value = list[0].checkpoint_id
      forkForm.checkpointId = list[0].checkpoint_id
    }
  },
  { immediate: true }
)

const handleSelectCheckpoint = async (cpId) => {
  selectedCpId.value = cpId
  forkForm.checkpointId = cpId
  activeTab.value = 'inspect'
  loadingInspect.value = true
  try {
    inspectResult.value = await store.inspectCheckpoint(cpId)
  } finally {
    loadingInspect.value = false
  }
}

const quickFork = (cpId) => {
  selectedCpId.value = cpId
  forkForm.checkpointId = cpId
  activeTab.value = 'fork'
}

const renderedInspectMarkdown = computed(() => {
  if (!inspectResult.value?.document) return ''
  try {
    return marked.parse(inspectResult.value.document)
  } catch (err) {
    return inspectResult.value.document
  }
})

const submitFork = async () => {
  if (!forkForm.checkpointId) {
    message.error('请指定 Checkpoint ID')
    return
  }

  const revisedPlan = forkForm.revisedPlanStr
    ? forkForm.revisedPlanStr.split(/[;；\n]/).map(t => t.trim()).filter(Boolean)
    : []

  const removeSources = forkForm.removeSourcesStr
    ? forkForm.removeSourcesStr.split(/[\n,，]/).map(t => t.trim()).filter(Boolean)
    : []

  const removeTexts = forkForm.removeTextsStr
    ? forkForm.removeTextsStr.split('\n').map(t => t.trim()).filter(Boolean)
    : []

  const manualEvidence = forkForm.manualEvidenceStr
    ? forkForm.manualEvidenceStr.split('\n').map(t => t.trim()).filter(Boolean)
    : []

  await store.createForkBranch({
    checkpointId: forkForm.checkpointId,
    revisedPlan,
    removeSources,
    removeTexts,
    manualEvidence,
  })
}
</script>
