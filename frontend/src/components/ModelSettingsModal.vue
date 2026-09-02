<template>
  <a-modal
    :open="store.showModelSettingsModal"
    :closable="store.isLLMConfigured"
    :mask-closable="store.isLLMConfigured"
    :keyboard="store.isLLMConfigured"
    :footer="null"
    width="720px"
    @cancel="closeModal"
  >
    <div class="overflow-hidden rounded-2xl bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-100">
      <div class="relative px-7 pt-7 pb-6 border-b border-slate-200 dark:border-slate-800">
        <div class="absolute top-0 right-0 w-52 h-32 bg-cyan-400/10 dark:bg-cyan-400/5 blur-3xl pointer-events-none"></div>
        <div class="relative flex items-start gap-4">
          <div class="w-11 h-11 shrink-0 rounded-xl bg-slate-950 dark:bg-cyan-300 text-cyan-300 dark:text-slate-950 flex items-center justify-center shadow-lg">
            <KeyRound class="w-5 h-5" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-lg font-bold tracking-tight">模型连接设置</h2>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                BYOK
              </span>
            </div>
            <p class="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400 max-w-xl">
              使用你自己的 API Key。密钥仅保存在服务端当前会话内存，不写入浏览器存储、数据库、Checkpoint 或日志。
            </p>
          </div>
        </div>
      </div>

      <form class="px-7 py-6" @submit.prevent="save">
        <div class="grid grid-cols-2 gap-3 mb-6">
          <button
            v-for="option in providers"
            :key="option.value"
            type="button"
            @click="form.provider = option.value"
            :class="[
              'relative text-left rounded-xl border p-4 transition-all cursor-pointer',
              form.provider === option.value
                ? 'border-cyan-500 bg-cyan-50/70 dark:bg-cyan-950/20 shadow-sm shadow-cyan-500/10'
                : 'border-slate-200 dark:border-slate-800 hover:border-slate-400 dark:hover:border-slate-600'
            ]"
          >
            <CheckCircle2
              v-if="form.provider === option.value"
              class="absolute right-3 top-3 w-4 h-4 text-cyan-600 dark:text-cyan-300"
            />
            <div class="text-sm font-bold">{{ option.label }}</div>
            <div class="mt-1 text-[11px] leading-4 text-slate-500 dark:text-slate-400">
              {{ option.description }}
            </div>
          </button>
        </div>

        <div class="space-y-4">
          <label class="block">
            <span class="flex items-center justify-between text-xs font-semibold mb-1.5">
              <span>API Key</span>
              <span class="text-[10px] font-normal text-slate-400">保存后不会再次显示</span>
            </span>
            <div class="relative">
              <input
                v-model="form.api_key"
                :type="showKey ? 'text' : 'password'"
                required
                autocomplete="off"
                spellcheck="false"
                :placeholder="form.provider === 'openai' ? 'sk-...' : '输入 DeepSeek API Key'"
                class="w-full h-11 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 pl-3.5 pr-11 text-sm font-mono outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/10 transition"
              />
              <button
                type="button"
                @click="showKey = !showKey"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer"
                :aria-label="showKey ? '隐藏 API Key' : '显示 API Key'"
              >
                <EyeOff v-if="showKey" class="w-4 h-4" />
                <Eye v-else class="w-4 h-4" />
              </button>
            </div>
          </label>

          <template v-if="form.provider === 'openai'">
            <div class="grid sm:grid-cols-2 gap-4">
              <ModelInput v-model="form.openai_model" label="生成模型" hint="Planner / Writer / Reviewer" />
              <ModelInput v-model="form.openai_search_model" label="搜索模型" hint="Research Worker + Web Search" />
            </div>
          </template>

          <template v-else>
            <ModelInput v-model="form.deepseek_model" label="DeepSeek 模型" hint="所有研究节点" />
            <label class="block">
              <span class="block text-xs font-semibold mb-1.5">Base URL</span>
              <input
                v-model="form.deepseek_base_url"
                required
                spellcheck="false"
                class="w-full h-11 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3.5 text-sm font-mono outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/10 transition"
              />
              <span class="block mt-1 text-[10px] text-amber-600 dark:text-amber-400">
                自定义地址会让服务端向该地址发送 API Key；仅使用你信任的 HTTPS 服务。
              </span>
            </label>
          </template>
        </div>

        <div class="mt-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-5 border-t border-slate-200 dark:border-slate-800">
          <div class="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
            <ShieldCheck class="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>会话最长保留 12 小时，服务重启后立即清除。</span>
          </div>
          <div class="flex items-center justify-end gap-2">
            <button
              v-if="store.isLLMConfigured"
              type="button"
              @click="clearConfig"
              class="px-3.5 py-2 rounded-lg text-xs font-medium text-rose-600 dark:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition cursor-pointer"
            >
              清除密钥
            </button>
            <button
              v-if="store.isLLMConfigured"
              type="button"
              @click="closeModal"
              class="px-3.5 py-2 rounded-lg text-xs font-medium text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-900 transition cursor-pointer"
            >
              取消
            </button>
            <button
              type="submit"
              :disabled="saving || !form.api_key.trim()"
              class="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold bg-slate-950 hover:bg-slate-800 dark:bg-cyan-300 dark:hover:bg-cyan-200 text-white dark:text-slate-950 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg transition cursor-pointer"
            >
              <LoaderCircle v-if="saving" class="w-4 h-4 animate-spin" />
              <Save v-else class="w-4 h-4" />
              <span>{{ saving ? '正在保存' : '保存并启用' }}</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  </a-modal>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import {
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LoaderCircle,
  Save,
  ShieldCheck,
} from 'lucide-vue-next'
import { useResearchStore } from '../stores/research'
import ModelInput from './ModelInput.vue'

const store = useResearchStore()
const saving = ref(false)
const showKey = ref(false)
const providers = [
  {
    value: 'openai',
    label: 'OpenAI',
    description: 'Responses API、结构化输出与原生 Web Search。',
  },
  {
    value: 'deepseek',
    label: 'DeepSeek',
    description: 'DeepSeek Responses / Chat 接口与服务端搜索。',
  },
]

const form = reactive({
  provider: 'openai',
  api_key: '',
  openai_model: 'gpt-5-mini',
  openai_search_model: 'gpt-5.4-mini',
  deepseek_model: 'deepseek-v4-flash',
  deepseek_base_url: 'https://api.deepseek.com',
})

watch(
  () => store.showModelSettingsModal,
  (open) => {
    if (!open || !store.config) return
    form.provider = store.config.provider || 'openai'
    form.api_key = ''
    form.openai_model = store.config.openai_model || 'gpt-5-mini'
    form.openai_search_model = store.config.openai_search_model || 'gpt-5.4-mini'
    form.deepseek_model = store.config.deepseek_model || 'deepseek-v4-flash'
    form.deepseek_base_url = store.config.deepseek_base_url || 'https://api.deepseek.com'
    showKey.value = false
  },
)

const closeModal = () => {
  if (store.isLLMConfigured) {
    store.showModelSettingsModal = false
  }
}

const save = async () => {
  if (!form.api_key.trim()) return
  saving.value = true
  try {
    await store.saveModelConfig({ ...form })
    form.api_key = ''
  } finally {
    saving.value = false
  }
}

const clearConfig = async () => {
  form.api_key = ''
  await store.clearModelConfig()
}
</script>
