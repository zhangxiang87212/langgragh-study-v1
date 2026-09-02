<template>
  <label class="block">
    <span class="block text-xs font-semibold mb-1.5">{{ label }}</span>
    <input
      :value="modelValue"
      required
      spellcheck="false"
      class="w-full h-11 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3.5 text-sm font-mono outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/10 transition"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <span class="block mt-1 text-[10px] text-slate-400">{{ hint }}</span>
  </label>
</template>

<script setup>
defineProps({
  modelValue: { type: String, required: true },
  label: { type: String, required: true },
  hint: { type: String, required: true },
})

defineEmits(['update:modelValue'])
</script>
