<template>
  <div class="glass-card rounded-2xl p-4 border border-slate-200/90 dark:border-slate-800/80 mb-6 relative overflow-hidden transition-colors">
    <!-- Background subtle gradient glow -->
    <div class="absolute -right-20 -top-20 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="flex items-center justify-between mb-3 px-1">
      <div class="flex items-center space-x-2">
        <GitFork class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
        <span class="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">LangGraph 节点状态流</span>
      </div>
      <div class="text-[11px] text-slate-500 dark:text-slate-400">
        当前线程: <span class="font-mono text-slate-700 dark:text-slate-300">{{ store.currentThreadId || '未选择' }}</span>
      </div>
    </div>

    <!-- Node Pipeline Steps -->
    <div class="flex items-center justify-between relative overflow-x-auto py-2 px-1">
      <div
        v-for="(step, idx) in steps"
        :key="step.id"
        class="flex items-center flex-1 min-w-[120px] last:flex-none relative"
      >
        <!-- Node Box -->
        <div
          :class="[
            'flex flex-col items-center justify-center p-2.5 rounded-xl border transition-all duration-300 w-full relative z-10',
            getNodeStatusClass(step.id)
          ]"
        >
          <!-- Icon & status dot -->
          <div class="flex items-center space-x-1.5 mb-1">
            <component :is="step.icon" class="w-3.5 h-3.5" :class="getIconColor(step.id)" />
            <span class="text-xs font-medium">{{ step.title }}</span>
          </div>

          <span class="text-[10px] text-slate-500 dark:text-slate-400">{{ step.subtitle }}</span>

          <!-- Active pulsing ring -->
          <span
            v-if="isActive(step.id)"
            class="absolute -inset-0.5 rounded-xl border border-indigo-400 animate-ping opacity-50 pointer-events-none"
          ></span>
        </div>

        <!-- Connector Line (except for last) -->
        <div
          v-if="idx < steps.length - 1"
          class="h-[2px] w-6 flex-shrink-0 mx-1 transition-colors duration-300"
          :class="isCompleted(step.id) ? 'bg-indigo-500/80' : 'bg-slate-200 dark:bg-slate-800'"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  GitFork,
  BrainCircuit,
  UserCheck,
  Search,
  CheckCheck,
  FileEdit,
  Star,
} from 'lucide-vue-next'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()

const steps = [
  { id: 'planner', title: 'Planner', subtitle: '规划任务', icon: BrainCircuit },
  { id: 'plan_approval', title: 'Approval', subtitle: '人工确认', icon: UserCheck },
  { id: 'research_worker', title: 'Workers', subtitle: '并行检索', icon: Search },
  { id: 'research_evaluator', title: 'Evaluator', subtitle: '质量评估', icon: CheckCheck },
  { id: 'writer', title: 'Writer', subtitle: '撰写研报', icon: FileEdit },
  { id: 'reviewer', title: 'Reviewer', subtitle: '审核打分', icon: Star },
]

const isActive = (nodeId) => {
  return store.activeNode === nodeId || (nodeId === 'research_worker' && store.activeNode === 'prepare_research')
}

const isCompleted = (nodeId) => {
  if (store.executionStatus === 'completed') return true
  return store.completedNodes.includes(nodeId)
}

const isWaitingApproval = (nodeId) => {
  return nodeId === 'plan_approval' && store.executionStatus === 'waiting_approval'
}

const getNodeStatusClass = (nodeId) => {
  if (isWaitingApproval(nodeId)) {
    return 'bg-amber-50 dark:bg-amber-950/60 border-amber-400 dark:border-amber-500/80 text-amber-800 dark:text-amber-200 shadow-lg shadow-amber-500/20 animate-pulse'
  }
  if (isActive(nodeId)) {
    return 'bg-indigo-50 dark:bg-indigo-950/80 border-indigo-500 text-indigo-700 dark:text-indigo-100 shadow-lg shadow-indigo-500/25 ring-1 ring-indigo-400/40'
  }
  if (isCompleted(nodeId)) {
    return 'bg-white dark:bg-slate-900/90 border-emerald-400/60 dark:border-emerald-500/40 text-slate-800 dark:text-slate-200'
  }
  return 'bg-slate-50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-800/60 text-slate-400 dark:text-slate-500 opacity-60'
}

const getIconColor = (nodeId) => {
  if (isWaitingApproval(nodeId)) return 'text-amber-500 dark:text-amber-400'
  if (isActive(nodeId)) return 'text-indigo-600 dark:text-indigo-400'
  if (isCompleted(nodeId)) return 'text-emerald-600 dark:text-emerald-400'
  return 'text-slate-400 dark:text-slate-500'
}
</script>
