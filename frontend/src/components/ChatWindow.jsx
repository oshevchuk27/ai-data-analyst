import React, { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble.jsx'

const EXAMPLES = [
  'Fetch AAPL stock prices for the last 60 days, plot a line chart, and compute mean, median, and standard deviation',
  'Generate 12 months of sample sales data, compute a 3-month rolling average, and plot both',
  'Create 200 random normal values, show descriptive statistics, and plot a histogram',
  'Compare monthly returns of TSLA vs MSFT over the past year and run a t-test',
]

export default function ChatWindow({ messages, loading, onExample }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const isEmpty = messages.length === 0

  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '24px 20px',
      display: 'flex', flexDirection: 'column', gap: 20,
    }}>
      {isEmpty ? (
        <div style={{ margin: 'auto', textAlign: 'center', maxWidth: 480 }}>
          <div style={{
            width: 52, height: 52, background: '#1D9E75',
            borderRadius: 14, display: 'flex', alignItems: 'center',
            justifyContent: 'center', margin: '0 auto 20px',
            fontSize: 24,
          }}>🧪</div>
          <h1 style={{ fontSize: 20, fontWeight: 500, marginBottom: 8, color: '#e2e8f0' }}>
            AI Data Analysis Agent
          </h1>
          <p style={{ fontSize: 14, color: '#718096', lineHeight: 1.7, marginBottom: 24 }}>
            Describe your data analysis needs in plain English. The React agent will guide you through
            the analysis process using reasoning and structured problem-solving.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {EXAMPLES.map((ex, i) => (
              <button key={i} onClick={() => onExample(ex)} style={{
                background: '#1e2533', border: '1px solid #2d3748',
                borderRadius: 8, padding: '10px 14px', color: '#a0aec0',
                fontSize: 12, cursor: 'pointer', textAlign: 'left', lineHeight: 1.5,
                fontFamily: 'inherit',
              }}
                onMouseEnter={e => e.target.style.borderColor = '#1D9E75'}
                onMouseLeave={e => e.target.style.borderColor = '#2d3748'}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          {messages.map((msg, i) => <MessageBubble key={i} message={msg} />)}
          {loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {['🤔 Thinking about your request...', '🎯 Planning analysis approach...', '💡 Generating insights...'].map((step, i) => (
                <div key={i} style={{
                  fontSize: 12, color: '#718096',
                  animation: `fadeIn 0.4s ease ${i * 0.6}s both`,
                }}>
                  {step}
                </div>
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </>
      )}
      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }`}</style>
    </div>
  )
}
