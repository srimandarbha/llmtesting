import React, { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, HistoricalSummary } from '../api/client'
import { format } from 'date-fns'

interface Message {
  role: 'user' | 'agent'
  content: string
}

export const Summaries: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'history'>('chat')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [timeframe, setTimeframe] = useState<number>(8)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [previewText, setPreviewText] = useState('')
  const [shiftName, setShiftName] = useState('')

  const [showCommands, setShowCommands] = useState(false)
  const availableCommands = [
    { cmd: '/checkalerts', desc: 'View active alerts (e.g. /checkalerts nzclu101)' },
    { cmd: '/escalate', desc: 'Escalate an incident to CRITICAL (e.g. /escalate INC123)' }
  ]

  const queryClient = useQueryClient()

  // 30-min window logic
  const [isWithinWindow, setIsWithinWindow] = useState(false)
  useEffect(() => {
    const checkWindow = () => {
      const now = new Date()
      const hour = now.getHours()
      const minute = now.getMinutes()
      const isShiftStart = (hour === 0 || hour === 8 || hour === 16)
      setIsWithinWindow(isShiftStart && minute <= 30)
    }
    checkWindow()
    const interval = setInterval(checkWindow, 60000)
    return () => clearInterval(interval)
  }, [])

  const chatMutation = useMutation({
    mutationFn: api.chatWithContext,
    onSuccess: (data) => {
      setMessages(prev => [...prev, { role: 'agent', content: data.answer }])
    },
    onError: (error) => {
      setMessages(prev => [...prev, { role: 'agent', content: `Error: ${error.message}` }])
    }
  })

  const previewMutation = useMutation({
    mutationFn: api.previewSummary,
    onSuccess: (data) => {
      setShiftName(data.shift_name)
      setPreviewText(data.preview_text)
      setShowPreviewModal(true)
    }
  })

  const saveMutation = useMutation({
    mutationFn: api.saveSummary,
    onSuccess: () => {
      setShowPreviewModal(false)
      queryClient.invalidateQueries({ queryKey: ['historical_summaries'] })
    }
  })

  const { data: historical } = useQuery({
    queryKey: ['historical_summaries'],
    queryFn: api.getHistoricalSummaries,
    enabled: activeTab === 'history',
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = (text: string) => {
    if (!text.trim()) return
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInput('')
    chatMutation.mutate({ query: text, timeframe_hours: timeframe })
  }

  const handleQuickAction = (hours: number, promptText: string) => {
    setTimeframe(hours)
    handleSend(promptText)
  }

  return (
    <div className="max-w-5xl mx-auto h-[calc(100vh-8rem)] flex flex-col animate-fade-in relative">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">
            SRE <span className="text-gradient">Summaries</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Persisted shift reports and intelligent query assistant.
          </p>
        </div>
        
        <button 
          onClick={() => previewMutation.mutate()}
          className="btn btn-primary"
          disabled={!isWithinWindow || previewMutation.isPending}
          title={!isWithinWindow ? "Only enabled during the first 30 mins of a shift (00:00, 08:00, 16:00)" : ""}
        >
          {previewMutation.isPending ? 'Generating...' : '📝 Generate Previous Shift Summary'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-4 border-b border-white/10 pb-2">
        <button 
          className={`text-sm font-semibold pb-2 border-b-2 transition-colors ${activeTab === 'chat' ? 'border-brand-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
          onClick={() => setActiveTab('chat')}
        >
          💬 AI Chat Assistant
        </button>
        <button 
          className={`text-sm font-semibold pb-2 border-b-2 transition-colors ${activeTab === 'history' ? 'border-brand-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
          onClick={() => setActiveTab('history')}
        >
          📚 Historical Shift Reports
        </button>
      </div>

      {activeTab === 'chat' && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex gap-3 mb-4">
            <button 
              onClick={() => handleQuickAction(8, "Please summarize the main incidents and handovers from the last 8 hours.")}
              className="btn btn-ghost border border-white/10 text-xs"
              disabled={chatMutation.isPending}
            >
              ⏱️ Last 8 Hours (Shift Sync)
            </button>
            <button 
              onClick={() => handleQuickAction(168, "Please summarize the critical issues, flapping alerts, and major activities from the last week.")}
              className="btn btn-ghost border border-white/10 text-xs"
              disabled={chatMutation.isPending}
            >
              📅 Last 1 Week (Vector Search)
            </button>
            
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs text-slate-500">Context Window:</span>
              <select 
                value={timeframe} 
                onChange={e => setTimeframe(Number(e.target.value))}
                className="bg-surface-700 text-xs text-slate-200 px-2 py-1 rounded border border-white/10 focus:outline-none focus:border-brand-500"
              >
                <option value={8}>8 Hours</option>
                <option value={24}>24 Hours</option>
                <option value={168}>1 Week</option>
              </select>
            </div>
          </div>

          <div className="flex-1 glass-card overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500">
                  <span className="text-4xl mb-4 opacity-50">🤖</span>
                  <p>I perform semantic vector searches across historical shift reports.</p>
                </div>
              ) : (
                messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-xl px-5 py-3 ${
                      msg.role === 'user' 
                        ? 'bg-brand-600 text-white shadow-lg shadow-brand-900/20' 
                        : 'bg-surface-600 text-slate-200 border border-white/5'
                    }`}>
                      <div className="text-xs font-semibold opacity-50 mb-1 uppercase tracking-wider">
                        {msg.role === 'user' ? 'You' : 'AI Agent'}
                      </div>
                      <div className="whitespace-pre-wrap text-sm">
                        {msg.content}
                      </div>
                    </div>
                  </div>
                ))
              )}
              {chatMutation.isPending && (
                <div className="flex justify-start">
                  <div className="bg-surface-600 border border-white/5 rounded-xl px-5 py-3 text-slate-400 text-sm flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                    Searching vectors & summarizing...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="p-4 border-t border-white/5 bg-surface-800/50">
              <form 
                onSubmit={e => {
                  e.preventDefault()
                  setShowCommands(false)
                  handleSend(input)
                }}
                className="flex gap-3 relative"
              >
                {showCommands && (
                  <div className="absolute bottom-full left-0 mb-2 w-full max-w-md bg-surface-800 border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-fade-in z-50">
                    <div className="p-2 bg-surface-900 border-b border-white/5 text-xs text-brand-400 font-semibold uppercase tracking-wider">
                      Available Commands
                    </div>
                    {availableCommands.filter(c => c.cmd.startsWith(input.split(' ')[0])).length === 0 ? (
                      <div className="p-3 text-sm text-slate-500">No matching commands.</div>
                    ) : (
                      availableCommands
                        .filter(c => c.cmd.startsWith(input.split(' ')[0]))
                        .map(c => (
                          <button
                            key={c.cmd}
                            type="button"
                            className="w-full text-left p-3 hover:bg-surface-700 transition-colors flex flex-col border-b border-white/5 last:border-0"
                            onClick={() => {
                              setInput(c.cmd + ' ')
                              setShowCommands(false)
                            }}
                          >
                            <span className="font-mono text-brand-300 font-bold">{c.cmd}</span>
                            <span className="text-xs text-slate-400 mt-1">{c.desc}</span>
                          </button>
                      ))
                    )}
                  </div>
                )}
                <input
                  type="text"
                  value={input}
                  onChange={e => {
                    setInput(e.target.value)
                    setShowCommands(e.target.value.startsWith('/'))
                  }}
                  placeholder="Ask about historical alerts or type / for commands..."
                  className="input flex-1"
                  disabled={chatMutation.isPending}
                />
                <button 
                  type="submit" 
                  className="btn btn-primary px-6"
                  disabled={chatMutation.isPending || !input.trim()}
                >
                  Send
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div className="flex-1 overflow-y-auto space-y-4">
          {!historical || historical.length === 0 ? (
            <div className="glass-card p-8 text-center text-slate-500">
              No historical shift summaries found.
            </div>
          ) : (
            historical.map((h: HistoricalSummary) => (
              <div key={h.id} className="glass-card p-6 border-l-4 border-brand-500">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-white text-lg">{h.shift_name}</h3>
                    <p className="text-xs text-slate-400 mt-1">
                      {format(new Date(h.created_at), 'PPPppp')} 
                      {h.is_auto_generated ? ' (Auto-Generated via Celery)' : ' (Manually Saved)'}
                    </p>
                  </div>
                </div>
                <div className="text-sm text-slate-300 whitespace-pre-wrap bg-surface-800/50 p-4 rounded-lg border border-white/5">
                  {h.summary_text}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Preview Modal */}
      {showPreviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-800 border border-white/10 rounded-xl w-full max-w-4xl shadow-2xl flex flex-col max-h-[90vh]">
            <div className="p-6 border-b border-white/10 flex justify-between items-center">
              <h2 className="text-lg font-bold text-white">Review Shift Report: {shiftName}</h2>
              <button className="text-slate-400 hover:text-white" onClick={() => setShowPreviewModal(false)}>✕</button>
            </div>
            <div className="p-6 flex-1 overflow-hidden flex flex-col">
              <label className="block text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">Generated Text (Editable)</label>
              <textarea 
                className="input w-full flex-1 resize-none font-mono text-sm"
                value={previewText}
                onChange={e => setPreviewText(e.target.value)}
              />
            </div>
            <div className="p-6 border-t border-white/10 flex justify-end gap-3 bg-surface-900/50">
              <button className="btn btn-ghost" onClick={() => setShowPreviewModal(false)}>Cancel</button>
              <button 
                className="btn btn-primary"
                disabled={saveMutation.isPending}
                onClick={() => saveMutation.mutate({ shift_name: shiftName, summary_text: previewText })}
              >
                {saveMutation.isPending ? 'Saving...' : 'Save & Vectorize Report'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
