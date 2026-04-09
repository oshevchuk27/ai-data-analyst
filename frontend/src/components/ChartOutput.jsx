import React from 'react'

export default function ChartOutput({ plots }) {
  if (!plots || plots.length === 0) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 12 }}>
      {plots.map((b64, i) => (
        <div key={i} style={{
          background: '#1a202c', borderRadius: 8,
          border: '1px solid #2d3748', overflow: 'hidden'
        }}>
          <div style={{
            padding: '5px 12px', background: '#16213e',
            fontSize: 10, color: '#718096', fontFamily: 'monospace'
          }}>
            figure {i + 1}
          </div>
          <img
            src={`data:image/png;base64,${b64}`}
            alt={`Chart output ${i + 1}`}
            style={{ width: '100%', display: 'block' }}
          />
        </div>
      ))}
    </div>
  )
}
