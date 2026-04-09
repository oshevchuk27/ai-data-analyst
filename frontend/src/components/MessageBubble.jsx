import React from 'react'
import CodeBlock from './CodeBlock.jsx'
import ChartOutput from './ChartOutput.jsx'

const S = {
  wrap: (role) => ({
    display: 'flex',
    flexDirection: 'column',
    alignItems: role === 'user' ? 'flex-end' : 'flex-start',
    gap: 8,
    maxWidth: '100%',
  }),
  userBubble: {
    background: '#1D9E75',
    color: 'white',
    padding: '10px 14px',
    borderRadius: '14px 14px 4px 14px',
    fontSize: 14,
    lineHeight: 1.6,
    maxWidth: '80%',
    whiteSpace: 'pre-wrap',
  },
  assistantBubble: {
    background: '#1e2533',
    border: '1px solid #2d3748',
    color: '#e2e8f0',
    padding: '10px 14px',
    borderRadius: '14px 14px 14px 4px',
    fontSize: 14,
    lineHeight: 1.7,
    maxWidth: '90%',
    whiteSpace: 'pre-wrap',
  },
  outputBox: {
    background: '#0d1117',
    border: '1px solid #2d3748',
    borderRadius: 8,
    padding: '10px 14px',
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#68d391',
    whiteSpace: 'pre-wrap',
    maxWidth: '90%',
    maxHeight: 200,
    overflowY: 'auto',
    lineHeight: 1.8,
  },
  errorBox: {
    background: '#2d1515',
    border: '1px solid #c53030',
    borderRadius: 8,
    padding: '10px 14px',
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#fc8181',
    whiteSpace: 'pre-wrap',
    maxWidth: '90%',
  },
  label: {
    fontSize: 10,
    color: '#718096',
    fontFamily: 'monospace',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    marginBottom: 2,
  },
}

export default function MessageBubble({ message }) {
  const { role, content, result } = message

  if (role === 'user') {
    return (
      <div style={S.wrap('user')}>
        <div style={S.userBubble}>{content}</div>
      </div>
    )
  }

  // Assistant message — may have structured result
  if (!result) {
    return (
      <div style={S.wrap('assistant')}>
        <div style={S.assistantBubble}>{content}</div>
      </div>
    )
  }

  const { code, output, error, summary, plots } = result

  return (
    <div style={S.wrap('assistant')}>
      {code && (
        <div style={{ maxWidth: '90%', width: '100%' }}>
          <div style={S.label}>generated code</div>
          <CodeBlock code={code} />
        </div>
      )}

      {output && (
        <div style={{ maxWidth: '90%', width: '100%' }}>
          <div style={S.label}>stdout</div>
          <div style={S.outputBox}>{output}</div>
        </div>
      )}

      {error && (
        <div style={{ maxWidth: '90%', width: '100%' }}>
          <div style={S.label}>error (auto-corrected)</div>
          <div style={S.errorBox}>{error}</div>
        </div>
      )}

      <ChartOutput plots={plots} />

      {summary && (
        <div style={S.assistantBubble}>{summary}</div>
      )}
    </div>
  )
}
