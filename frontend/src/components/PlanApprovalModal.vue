<template>
  <a-modal
    :open="store.showApprovalModal"
    :title="null"
    :footer="null"
    :closable="true"
    @cancel="handleClose"
    width="680px"
    class="custom-approval-modal"
  >
    <div class="p-2 text-slate-800 dark:text-slate-100">
      <!-- Modal Header -->
      <div class="flex items-center space-x-3 mb-4">
        <div class="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-600 dark:text-amber-400">
          <UserCheck class="w-5 h-5" />
        </div>
        <div>
          <h3 class="text-base font-bold text-slate-900 dark:text-slate-100">
            人机协同审批：确认或修改研究计划
          </h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            LangGraph 流程已在 <code class="text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-950/60 px-1 py-0.5 rounded">plan_approval</code> 节点暂停，等待您的审查。
          </p>
        </div>
      </div>

      <!-- Topic Alert -->
      <div class="bg-slate-100 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl p-3 mb-4 text-xs">
        <span class="text-slate-500 dark:text-slate-400">当前研究主题：</span>
        <span class="text-indigo-600 dark:text-indigo-300 font-semibold ml-1">{{ store.topic }}</span>
      </div>

      <!-- Task List Editable -->
      <div class="space-y-3 mb-5 max-h-[380px] overflow-y-auto pr-1">
        <div class="flex items-center justify-between text-xs font-semibold text-slate-700 dark:text-slate-300 px-1">
          <span>研究子任务列表 ({{ taskList.length }} 项)</span>
          <button
            @click="addTask"
            class="inline-flex items-center space-x-1 text-xs text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
          >
            <Plus class="w-3.5 h-3.5" />
            <span>添加任务</span>
          </button>
        </div>

        <div
          v-for="(task, idx) in taskList"
          :key="idx"
          class="flex items-center space-x-2 bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800/80 rounded-xl p-2.5 transition-all focus-within:border-indigo-500/50"
        >
          <span class="flex-shrink-0 w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/50 flex items-center justify-center text-xs font-mono font-bold">
            {{ idx + 1 }}
          </span>

          <input
            v-model="taskList[idx]"
            type="text"
            placeholder="输入研究任务描述..."
            class="flex-1 bg-transparent border-none text-xs text-slate-800 dark:text-slate-200 focus:outline-none placeholder-slate-400 dark:placeholder-slate-500"
          />

          <button
            @click="removeTask(idx)"
            class="p-1 rounded text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors cursor-pointer"
            title="删除此任务"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Bottom Action Buttons -->
      <div class="flex items-center justify-end space-x-3 pt-3 border-t border-slate-200 dark:border-slate-800">
        <button
          @click="handleClose"
          class="px-4 py-2 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          稍后处理
        </button>

        <button
          @click="handleReviseSubmit"
          class="px-4 py-2 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-indigo-600 dark:text-indigo-300 border border-slate-200 dark:border-indigo-500/30 transition-all cursor-pointer"
        >
          提交修改并执行 ({{ taskList.length }} 项)
        </button>

        <button
          @click="handleDirectApprove"
          class="inline-flex items-center space-x-1.5 px-5 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white shadow-md shadow-emerald-600/25 transition-all cursor-pointer"
        >
          <Check class="w-4 h-4" />
          <span>直接批准原计划</span>
        </button>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { UserCheck, Plus, Trash2, Check } from 'lucide-vue-next'
import { message } from 'ant-design-vue'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()
const taskList = ref([])

watch(
  () => store.plan,
  (newPlan) => {
    if (newPlan && newPlan.length) {
      taskList.value = [...newPlan]
    }
  },
  { immediate: true }
)

const addTask = () => {
  taskList.value.push('')
}

const removeTask = (index) => {
  if (taskList.value.length <= 1) {
    message.warning('至少需要保留 1 个研究任务')
    return
  }
  taskList.value.splice(index, 1)
}

const handleClose = () => {
  store.showApprovalModal = false
}

const handleDirectApprove = () => {
  store.resumeWithApproval(true)
}

const handleReviseSubmit = () => {
  const cleaned = taskList.value.map(t => t.trim()).filter(Boolean)
  if (!cleaned.length) {
    message.error('研究计划不能为空')
    return
  }
  store.resumeWithApproval(false, cleaned)
}
</script>
