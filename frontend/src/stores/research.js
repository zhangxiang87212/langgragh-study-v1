import { defineStore } from 'pinia'
import api from '../api/client'
import { message } from 'ant-design-vue'

export const useResearchStore = defineStore('research', {
  state: () => ({
    // System Config
    config: null,
    
    // Thread List & Active Thread
    threads: [],
    currentThreadId: null,
    
    // Task Execution State
    isStreaming: false,
    executionStatus: 'idle', // 'idle' | 'running' | 'waiting_approval' | 'completed' | 'error'
    activeNode: null,
    completedNodes: [],
    
    // Core Research State
    topic: '',
    plan: [],
    planApproved: false,
    researchResults: [],
    researchContent: '',
    sources: [],
    researchScore: null,
    researchComment: '',
    
    // Report & Review
    draft: '',
    streamingDraftToken: '',
    reviewScore: null,
    reviewComment: '',
    revisionCount: 0,
    
    // Resilience & Usage
    budgetExhausted: false,
    terminationReason: '',
    usage: {
      llm_calls: 0,
      search_calls: 0,
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_usd: 0,
      estimated: true,
    },
    
    // Time Travel / Branching
    parentThreadId: null,
    parentCheckpointId: null,
    manualEvidence: [],
    checkpointHistory: [],
    inspectionData: null,
    
    // UI state controls
    showApprovalModal: false,
    showTimeTravelDrawer: false,
    showNewResearchModal: false,
    showModelSettingsModal: false,
    
    // Live logs stream
    liveLogs: [],
    
    // Internal EventSource instance
    eventSource: null,
  }),

  getters: {
    hasActiveThread: (state) => !!state.currentThreadId,
    isLLMConfigured: (state) => !!state.config?.configured,
    isWaitingApproval: (state) => state.executionStatus === 'waiting_approval',
    isFinished: (state) => state.executionStatus === 'completed',
    formattedCost: (state) => {
      const cost = state.usage?.cost_usd || 0
      return `$${cost.toFixed(4)}`
    },
    totalTokensFormatted: (state) => {
      const tokens = state.usage?.total_tokens || 0
      return tokens.toLocaleString()
    },
  },

  actions: {
    async fetchConfig() {
      try {
        this.config = await api.getConfig()
        if (!this.config.configured) {
          this.showModelSettingsModal = true
        }
      } catch (err) {
        console.error('Failed to load system config:', err)
        this.config = { configured: false }
        this.showModelSettingsModal = true
      }
    },

    async saveModelConfig(payload) {
      try {
        const savedConfig = await api.saveConfig(payload)
        this.config = { ...this.config, ...savedConfig }
        this.showModelSettingsModal = false
        message.success('模型配置已保存到当前服务端会话')
        return true
      } catch (err) {
        const detail = err.response?.data?.detail || err.message
        message.error(`保存模型配置失败：${detail}`)
        return false
      }
    },

    async clearModelConfig() {
      try {
        await api.clearConfig()
        this.config = { ...this.config, configured: false, api_key_configured: false }
        this.showModelSettingsModal = true
        message.success('当前会话中的 API Key 已清除')
      } catch (err) {
        const detail = err.response?.data?.detail || err.message
        message.error(`清除模型配置失败：${detail}`)
      }
    },

    async fetchThreads() {
      try {
        const res = await api.getThreads()
        this.threads = res.threads || []
      } catch (err) {
        console.error('Failed to fetch threads:', err)
      }
    },

    async selectThread(threadId) {
      if (!threadId) return
      this.closeStream()
      this.currentThreadId = threadId
      await this.loadThreadStatus(threadId)
      await this.loadThreadHistory(threadId)
    },

    async loadThreadStatus(threadId) {
      try {
        const data = await api.getStatus(threadId)
        this.topic = data.topic || ''
        this.executionStatus = data.status || 'idle'
        this.plan = data.plan || []
        this.planApproved = data.plan_approved || false
        this.researchResults = data.research_results || []
        this.researchContent = data.research_content || ''
        this.sources = data.sources || []
        this.researchScore = data.research_score
        this.researchComment = data.research_comment || ''
        this.draft = data.draft || ''
        this.reviewScore = data.review_score
        this.reviewComment = data.review_comment || ''
        this.revisionCount = data.revision_count || 0
        this.budgetExhausted = data.budget_exhausted || false
        this.terminationReason = data.termination_reason || ''
        this.usage = data.usage || this.usage
        this.parentThreadId = data.parent_thread_id
        this.parentCheckpointId = data.parent_checkpoint_id
        this.manualEvidence = data.manual_evidence || []

        if (this.executionStatus === 'waiting_approval') {
          this.showApprovalModal = true
          this.activeNode = 'plan_approval'
        } else if (this.executionStatus === 'completed') {
          this.activeNode = 'END'
          this.completedNodes = ['planner', 'plan_approval', 'research_worker', 'research_evaluator', 'writer', 'reviewer']
        }
      } catch (err) {
        console.error(`Failed to load thread ${threadId}:`, err)
        message.error(`加载线程状态失败: ${err.message}`)
      }
    },

    async loadThreadHistory(threadId) {
      try {
        const res = await api.getHistory(threadId)
        this.checkpointHistory = res.history || []
      } catch (err) {
        console.error(`Failed to load history for ${threadId}:`, err)
      }
    },

    async inspectCheckpoint(checkpointId = null) {
      if (!this.currentThreadId) return
      try {
        this.inspectionData = await api.inspectCheckpoint(this.currentThreadId, checkpointId)
        return this.inspectionData
      } catch (err) {
        console.error('Failed to inspect checkpoint:', err)
        message.error(`审查资料失败: ${err.message}`)
      }
    },

    startNewResearch(topic) {
      if (!this.isLLMConfigured) {
        this.showNewResearchModal = false
        this.showModelSettingsModal = true
        message.warning('请先配置模型和 API Key')
        return
      }
      this.closeStream()
      this.topic = topic
      this.draft = ''
      this.streamingDraftToken = ''
      this.plan = []
      this.planApproved = false
      this.researchResults = []
      this.sources = []
      this.researchScore = null
      this.researchComment = ''
      this.reviewScore = null
      this.reviewComment = ''
      this.completedNodes = []
      this.liveLogs = []
      this.executionStatus = 'running'
      this.activeNode = 'planner'

      // Generate local thread_id
      const threadId = `research-${Date.now()}`
      this.currentThreadId = threadId

      this.addLog(`🚀 启动新研究任务：${topic}`, 'info')
      this.listenStream(threadId, { action: 'run', topic })
    },

    resumeWithApproval(approved, revisedPlan = null) {
      if (!this.currentThreadId) return
      this.showApprovalModal = false
      this.executionStatus = 'running'
      this.activeNode = 'prepare_research'
      if (!this.completedNodes.includes('plan_approval')) {
        this.completedNodes.push('plan_approval')
      }

      if (approved) {
        this.addLog('🤝 人工审批：已批准研究计划，开始并行检索调研...', 'success')
      } else {
        this.plan = revisedPlan || this.plan
        this.addLog(`✍️ 人工审批：已修改研究计划（共 ${this.plan.length} 项），开始执行...`, 'warning')
      }

      const planStr = revisedPlan ? revisedPlan.join(';') : ''
      this.listenStream(this.currentThreadId, {
        action: 'resume',
        approve: approved,
        plan: planStr,
      })
    },

    async createForkBranch({ checkpointId, revisedPlan, removeSources, removeTexts, manualEvidence }) {
      if (!this.currentThreadId || !checkpointId) return
      try {
        message.loading({ content: '正在创建分支并准备时间旅行...', key: 'fork' })
        const res = await api.forkResearch({
          source_thread_id: this.currentThreadId,
          checkpoint_id: checkpointId,
          revised_plan: revisedPlan && revisedPlan.length ? revisedPlan : undefined,
          remove_sources: removeSources && removeSources.length ? removeSources : undefined,
          remove_texts: removeTexts && removeTexts.length ? removeTexts : undefined,
          manual_evidence: manualEvidence && manualEvidence.length ? manualEvidence : undefined,
        })

        message.success({ content: `分支创建成功：${res.new_thread_id}`, key: 'fork' })
        this.showTimeTravelDrawer = false
        
        // Switch to the newly created branch thread and stream
        await this.fetchThreads()
        this.currentThreadId = res.new_thread_id
        this.draft = ''
        this.streamingDraftToken = ''
        this.liveLogs = []
        this.addLog(`🌿 从快照 ${checkpointId.slice(0, 8)}... 创建修正分支：${res.new_thread_id}`, 'info')
        this.executionStatus = 'running'
        this.activeNode = res.next_node || 'prepare_research'

        this.listenStream(res.new_thread_id, { action: 'replay' })
      } catch (err) {
        message.error({ content: `创建分支失败: ${err.message}`, key: 'fork' })
      }
    },

    listenStream(threadId, streamParams) {
      this.closeStream()
      this.isStreaming = true

      const url = api.getStreamUrl(threadId, streamParams)
      this.eventSource = new EventSource(url)

      this.eventSource.addEventListener('status', (e) => {
        const data = JSON.parse(e.data)
        this.addLog(`⚡ 连接后端执行流: ${data.status}`, 'info')
      })

      this.eventSource.addEventListener('custom', (e) => {
        const data = JSON.parse(e.data)
        this.handleCustomEvent(data)
      })

      this.eventSource.addEventListener('updates', (e) => {
        const data = JSON.parse(e.data)
        this.handleUpdatesEvent(data)
      })

      this.eventSource.addEventListener('completed', (e) => {
        const data = JSON.parse(e.data)
        this.handleCompletedEvent(data)
      })

      this.eventSource.addEventListener('error', (e) => {
        let errData = '连接发生错误或意外断开'
        try {
          if (e.data) {
            const parsed = JSON.parse(e.data)
            errData = parsed.error || errData
          }
        } catch (_) {}
        this.addLog(`❌ 执行异常: ${errData}`, 'error')
        this.executionStatus = 'error'
        this.closeStream()
        this.fetchThreads()
      })
    },

    handleCustomEvent(data) {
      const type = data.event
      if (type === 'llm_stream_start') {
        const node = data.node
        this.activeNode = node
        this.addLog(`🧠 ${node} 模型开始流式生成...`, 'info')
        if (node === 'writer') {
          this.draft = ''
        }
      } else if (type === 'llm_token') {
        const token = data.text || ''
        if (data.node === 'writer') {
          this.draft += token
        }
      } else if (type === 'research_task_start') {
        this.activeNode = 'research_worker'
        this.addLog(`🔍 并行检索 [Worker ${data.task_number}/${data.task_count}]: ${data.task}`, 'info')
      } else if (type === 'research_task_result') {
        this.addLog(`✅ 检索完成 [Worker ${data.task_number}/${data.task_count}]: 找到 ${(data.sources || []).length} 个可信来源`, 'success')
        const existingIdx = this.researchResults.findIndex(r => r.task === data.task)
        const item = {
          task_index: data.task_number - 1,
          task: data.task,
          content: data.content,
          sources: data.sources || [],
        }
        if (existingIdx >= 0) {
          this.researchResults[existingIdx] = item
        } else {
          this.researchResults.push(item)
        }
        // Merge sources
        if (data.sources) {
          const set = new Set([...this.sources, ...data.sources])
          this.sources = Array.from(set)
        }
      }
    },

    handleUpdatesEvent(updates) {
      for (const [nodeName, nodeData] of Object.entries(updates)) {
        if (nodeName.startsWith('__')) continue

        this.addLog(`📌 节点完成：${nodeName}`, 'info')
        if (!this.completedNodes.includes(nodeName)) {
          this.completedNodes.push(nodeName)
        }

        if (nodeName === 'planner') {
          if (nodeData.plan) {
            this.plan = nodeData.plan
          }
          this.activeNode = 'plan_approval'
          this.executionStatus = 'waiting_approval'
          this.showApprovalModal = true
          this.addLog(`📋 Planner 已生成 ${this.plan.length} 个研究任务，等待人工审批...`, 'warning')
        } else if (nodeName === 'research_evaluator') {
          this.researchScore = nodeData.research_score
          this.researchComment = nodeData.research_comment
          this.activeNode = 'writer'
          this.addLog(`📊 资料评估得分: ${nodeData.research_score} / 100 (${nodeData.research_comment})`, 'info')
        } else if (nodeName === 'writer') {
          if (nodeData.draft) {
            this.draft = nodeData.draft
          }
          this.activeNode = 'reviewer'
          this.addLog(`📝 研报草稿编写完成，进入 Reviewer 评审...`, 'info')
        } else if (nodeName === 'reviewer') {
          this.reviewScore = nodeData.review_score
          this.reviewComment = nodeData.review_comment
          this.addLog(`⭐ 审阅评分: ${nodeData.review_score} / 100 (${nodeData.review_comment})`, 'info')
        }
      }
    },

    handleCompletedEvent(data) {
      this.closeStream()
      this.executionStatus = data.status || 'completed'
      if (data.plan) this.plan = data.plan
      if (data.draft) this.draft = data.draft
      if (data.review_score !== undefined) this.reviewScore = data.review_score
      if (data.review_comment) this.reviewComment = data.review_comment
      if (data.sources) this.sources = data.sources
      if (data.usage) this.usage = data.usage

      if (this.executionStatus === 'waiting_approval') {
        this.showApprovalModal = true
        this.activeNode = 'plan_approval'
      } else if (this.executionStatus === 'completed') {
        this.activeNode = 'END'
        this.addLog('🎉 研究任务已全部顺利完成！研报已就绪。', 'success')
      }

      this.fetchThreads()
      if (this.currentThreadId) {
        this.loadThreadHistory(this.currentThreadId)
      }
    },

    addLog(text, type = 'info') {
      const now = new Date().toLocaleTimeString()
      this.liveLogs.push({
        id: Math.random().toString(36).substring(2, 9),
        time: now,
        text,
        type,
      })
    },

    closeStream() {
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
      this.isStreaming = false
    },
  },
})
