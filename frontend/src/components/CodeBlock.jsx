import React, { useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

export default function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div style={{ borderRadius: 8, overflow: 'hidden', border: '1px solid #2d3748', marginBottom: 12 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '6px 14px', background: '#1a202c',
        fontSize: 11, color: '#718096', fontFamily: 'monospace'
      }}>
        <span>python</span>
        <button onClick={copy} style={{
          background: 'transparent', border: '1px solid #4a5568',
          color: '#a0aec0', borderRadius: 4, padding: '2px 8px',
          fontSize: 10, cursor: 'pointer'
        }}>
          {copied ? '✓ copied' : 'copy'}
        </button>
      </div>
      <SyntaxHighlighter
        language="python"
        style={vscDarkPlus}
        customStyle={{ margin: 0, borderRadius: 0, fontSize: 12, maxHeight: 360, overflowY: 'auto' }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}
