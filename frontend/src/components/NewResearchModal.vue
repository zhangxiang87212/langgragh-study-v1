<template>
  <a-modal
    :open="store.showNewResearchModal"
    :title="null"
    :footer="null"
    @cancel="store.showNewResearchModal = false"
    width="540px"
    class="custom-new-modal"
  >
    <div class="p-2 text-slate-800 dark:text-slate-100">
      <!-- Modal Header -->
      <div class="flex items-center space-x-3 mb-4">
        <div class="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-500/20 border border-indigo-200 dark:border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
          <Sparkles class="w-5 h-5" />
        </div>
        <div>
          <h3 class="text-base font-bold text-slate-900 dark:text-slate-100">
            发起新的深度研究任务
          </h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            输入主题，Mini Research Agent 将为您制定多维度研究方案
          </p>
        </div>
      </div>

      <!-- Topic Input -->
      <div class="mb-4">
        <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">研究主题 (Topic)</label>
        <textarea
          v-model="inputTopic"
          rows="3"
          placeholder="例如：AI Agent 在教育领域的发展趋势与商业化挑战..."
          class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors resize-none leading-relaxed"
          @keydown.enter.prevent="handleStart"
        ></textarea>
      </div>

      <!-- Preset Topics Recommendation -->
      <div class="mb-5">
        <span class="text-[11px] text-slate-500 block mb-2 font-medium">推荐研究方向：</span>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="preset in presets"
            :key="preset"
            @click="inputTopic = preset"
            class="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-900/90 hover:bg-slate-200 dark:hover:bg-slate-800 text-indigo-700 dark:text-indigo-300 border border-slate-200 dark:border-slate-800/80 hover:border-indigo-400 transition-all cursor-pointer text-left"
          >
            {{ preset }}
          </button>
        </div>
      </div>

      <!-- Action Footer -->
      <div class="flex items-center justify-end space-x-3 pt-3 border-t border-slate-200 dark:border-slate-800">
        <button
          @click="store.showNewResearchModal = false"
          class="px-4 py-2 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          取消
        </button>

        <button
          @click="handleStart"
          :disabled="!inputTopic.trim()"
          class="inline-flex items-center space-x-1.5 px-5 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-md shadow-indigo-600/30 transition-all cursor-pointer"
        >
          <Play class="w-3.5 h-3.5 fill-current" />
          <span>开始研究</span>
        </button>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref } from 'vue'
import { Sparkles, Play } from 'lucide-vue-next'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()
const inputTopic = ref('AI Agent 在教育领域的发展趋势')

const presets = [
  'AI Agent 在教育领域的发展趋势',
  '具身智能与多模态大模型在工业机器人中的融合',
  'DeepSeek 与 OpenAI 在推理模型上的架构对比',
  'LangGraph 在复杂企业级多智能体协同中的落地实践',
]

const handleStart = () => {
  if (!inputTopic.value.trim()) return
  store.showNewResearchModal = false
  store.startNewResearch(inputTopic.value.trim())
}
</script>
