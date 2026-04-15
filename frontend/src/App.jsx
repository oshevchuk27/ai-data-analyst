import React, { useState, useRef } from 'react'
import ChatWindow from './components/ChatWindow.jsx'
import { analyze } from './api.js'

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const textareaRef = useRef(null)

  // Build history from messages for context window
  const buildHistory = () =>
    messages.flatMap(msg => {
      if (msg.role === 'user') return [{ role: 'user', content: msg.content }]
      if (msg.role === 'assistant') {
        return [{ role: 'assistant', content: msg.content }]
      }
      return []
    })

  const submit = async (prompt) => {
    const text = (prompt || input).trim()
    if (!text || loading) return

    setInput('')
    setError(null)
    setLoading(true)

    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])

    try {
      const history = buildHistory()
      const result = await analyze(text, history)

      const assistantMsg = {
        role: 'assistant',
        content: result.summary,
        result,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setError(err.message)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}`,
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const autoResize = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* Sidebar */}
      <div style={{
        width: 220, minWidth: 220, background: '#0d1117',
        borderRight: '1px solid #1e2533', display: 'flex',
        flexDirection: 'column', padding: '20px 14px', gap: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 30, height: 30, background: '#1D9E75', borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 600, fontSize: 13, color: 'white',
          }}>ADA</div>
          <span style={{ fontWeight: 500, fontSize: 14, color: '#e2e8f0' }}>AI Data Analyst</span>
        </div>

        <div>
          <div style={{ fontSize: 10, color: '#4a5568', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
            Model
          </div>
          <div style={{ fontSize: 11, color: '#718096', fontFamily: 'monospace', lineHeight: 1.6 }}>
            claude-sonnet-4-20250514
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, color: '#4a5568', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
            React Agent
          </div>
          {['Think', 'Act', 'Observe', 'Respond'].map((step, i) => (
            <div key={i} style={{
              fontSize: 11, color: '#718096', padding: '3px 0',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#1D9E75', flexShrink: 0 }} />
              {step}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 'auto' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: '#0f2e22', border: '1px solid #1D9E75',
            borderRadius: 20, padding: '4px 10px',
            fontSize: 11, color: '#1D9E75',
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%', background: '#1D9E75',
              animation: 'pulse 2s ease-in-out infinite',
            }} />
            Agent active
          </div>
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#0f1117', overflow: 'hidden' }}>
        <ChatWindow
          messages={messages}
          loading={loading}
          onExample={(ex) => submit(ex)}
        />

        {/* Input area */}
        <div style={{
          borderTop: '1px solid #1e2533', padding: '12px 16px',
          display: 'flex', gap: 10, alignItems: 'flex-end',
          background: '#0d1117',
        }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => { setInput(e.target.value); autoResize() }}
            onKeyDown={handleKey}
            placeholder="Describe your data analysis task…"
            rows={1}
            style={{
              flex: 1, resize: 'none', border: '1px solid #2d3748',
              borderRadius: 10, padding: '10px 14px', fontSize: 14,
              fontFamily: 'inherit', lineHeight: 1.5, minHeight: 42,
              maxHeight: 140, color: '#e2e8f0', background: '#1e2533',
              outline: 'none', transition: 'border-color 0.15s',
            }}
            onFocus={e => e.target.style.borderColor = '#1D9E75'}
            onBlur={e => e.target.style.borderColor = '#2d3748'}
          />
          <button
            onClick={() => submit()}
            disabled={loading || !input.trim()}
            style={{
              width: 42, height: 42, background: loading || !input.trim() ? '#2d3748' : '#1D9E75',
              border: 'none', borderRadius: 10, cursor: loading ? 'not-allowed' : 'pointer',
              color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, transition: 'background 0.15s',
            }}
          >
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
              <path d="M1 7.5h13M7.5 1l6.5 6.5-6.5 6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      <style>{`
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 2px; }
      `}</style>
    </div>
  )
}
