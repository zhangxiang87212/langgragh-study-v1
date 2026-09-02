<template>
  <a-config-provider :theme="antdTheme">
    <div class="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col font-sans text-slate-800 dark:text-slate-100 selection:bg-indigo-500 selection:text-white transition-colors duration-200">
      <!-- Top Navbar -->
      <Navbar />

      <!-- Main Layout Body -->
      <div class="flex-1 flex overflow-hidden">
        <!-- Left Sidebar: Historical Tasks -->
        <ThreadSidebar />

        <!-- Center / Right Main Content Workspace -->
        <main class="flex-1 overflow-y-auto p-6 bg-slate-100/50 dark:bg-slate-950/40">
          <div class="max-w-7xl mx-auto space-y-6">
            <!-- Welcome View if no active thread selected -->
            <div v-if="!store.hasActiveThread" class="py-16 text-center max-w-2xl mx-auto">
              <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-xl shadow-indigo-500/20 mx-auto mb-5 ring-1 ring-white/20">
                <Sparkles class="w-8 h-8 text-white" />
              </div>
              <h2 class="text-2xl font-bold font-heading bg-clip-text text-transparent bg-gradient-to-r from-slate-900 via-slate-700 to-indigo-600 dark:from-white dark:via-slate-200 dark:to-indigo-300">
                Mini Research Agent 智能研报工作台
              </h2>
              <p class="text-xs text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">
                全自动多智能体协作：任务规划、人机审批、并行联网检索、质量评估、报告生成、多轮审阅与 Checkpoint 状态回溯
              </p>

              <div class="mt-8 flex justify-center space-x-4">
                <button
                  @click="store.showNewResearchModal = true"
                  class="inline-flex items-center space-x-2 px-6 py-3 rounded-xl text-xs font-semibold bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white shadow-lg shadow-indigo-600/30 transition-all cursor-pointer hover:scale-105"
                >
                  <Play class="w-4 h-4 fill-current" />
                  <span>立即发起研究</span>
                </button>
              </div>

              <!-- Feature Highlights -->
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-12 text-left">
                <div class="glass-card rounded-xl p-4 border border-slate-200 dark:border-slate-800">
                  <div class="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-3">
                    <BrainCircuit class="w-4 h-4" />
                  </div>
                  <h4 class="text-xs font-bold text-slate-800 dark:text-slate-200">多 Agent 并行检索</h4>
                  <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    由 Planner 分解任务，多 Worker 并发检索可信来源。
                  </p>
                </div>

                <div class="glass-card rounded-xl p-4 border border-slate-200 dark:border-slate-800">
                  <div class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-3">
                    <UserCheck class="w-4 h-4" />
                  </div>
                  <h4 class="text-xs font-bold text-slate-800 dark:text-slate-200">人机协同审批</h4>
                  <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    Graph 中断暂停机制，支持审查与自定义调整研究计划。
                  </p>
                </div>

                <div class="glass-card rounded-xl p-4 border border-slate-200 dark:border-slate-800">
                  <div class="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center mb-3">
                    <History class="w-4 h-4" />
                  </div>
                  <h4 class="text-xs font-bold text-slate-800 dark:text-slate-200">时间旅行与分支修正</h4>
                  <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    SQLite 快照持久化，支持回溯并从任意历史点 Fork 修正。
                  </p>
                </div>
              </div>
            </div>

            <!-- Active Research Workspace View -->
            <div v-else class="space-y-6">
              <!-- Topic Banner -->
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white/80 dark:bg-slate-900/60 p-4 rounded-2xl border border-slate-200/90 dark:border-slate-800/80 shadow-sm dark:shadow-none transition-colors">
                <div>
                  <span class="text-[10px] uppercase font-semibold tracking-wider text-indigo-600 dark:text-indigo-400 block mb-1">
                    当前研究主题 (Research Topic)
                  </span>
                  <h2 class="text-base font-bold text-slate-900 dark:text-slate-100">
                    {{ store.topic }}
                  </h2>
                </div>

                <div class="flex items-center space-x-2">
                  <button
                    v-if="store.isWaitingApproval"
                    @click="store.showApprovalModal = true"
                    class="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-amber-500/10 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30 dark:border-amber-500/40 hover:bg-amber-500/20 transition-all cursor-pointer animate-pulse flex items-center space-x-1.5"
                  >
                    <UserCheck class="w-3.5 h-3.5" />
                    <span>计划待审批</span>
                  </button>

                  <button
                    @click="store.showTimeTravelDrawer = true"
                    class="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-purple-600 dark:text-purple-300 border border-purple-300/40 dark:border-purple-500/30 transition-all cursor-pointer flex items-center space-x-1.5"
                  >
                    <History class="w-3.5 h-3.5 text-purple-500 dark:text-purple-400" />
                    <span>查看快照历史</span>
                  </button>
                </div>
              </div>

              <!-- Flow Step Indicator -->
              <GraphFlowIndicator />

              <!-- Main Split Layout: Left (Workers & Stats) vs Right (Report) -->
              <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                <!-- Left Column (5 cols) -->
                <div class="lg:col-span-5 space-y-6">
                  <!-- Research Workers & Evaluator -->
                  <ResearchMonitor />

                  <!-- Usage & Live Terminal -->
                  <UsageStatsCard />
                </div>

                <!-- Right Column (7 cols) -->
                <div class="lg:col-span-7">
                  <!-- Generated Report & Reviewer Feedback -->
                  <ReportViewer />
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      <!-- Modals & Drawers -->
      <PlanApprovalModal />
      <TimeTravelDrawer />
      <NewResearchModal />
      <ModelSettingsModal />
    </div>
  </a-config-provider>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { theme } from 'ant-design-vue'
import {
  Sparkles,
  Play,
  BrainCircuit,
  UserCheck,
  History,
} from 'lucide-vue-next'
import { useResearchStore } from './stores/research'
import { useThemeStore } from './stores/theme'
import Navbar from './components/Navbar.vue'
import ThreadSidebar from './components/ThreadSidebar.vue'
import GraphFlowIndicator from './components/GraphFlowIndicator.vue'
import PlanApprovalModal from './components/PlanApprovalModal.vue'
import ResearchMonitor from './components/ResearchMonitor.vue'
import ReportViewer from './components/ReportViewer.vue'
import UsageStatsCard from './components/UsageStatsCard.vue'
import TimeTravelDrawer from './components/TimeTravelDrawer.vue'
import NewResearchModal from './components/NewResearchModal.vue'
import ModelSettingsModal from './components/ModelSettingsModal.vue'

const store = useResearchStore()
const themeStore = useThemeStore()

const antdTheme = computed(() => ({
  algorithm: themeStore.isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
  token: {
    colorPrimary: '#6366f1',
    borderRadius: 8,
  },
}))

onMounted(async () => {
  themeStore.initTheme()
  await store.fetchConfig()
  await store.fetchThreads()
  if (store.threads && store.threads.length) {
    await store.selectThread(store.threads[0].thread_id)
  }
})
</script>
