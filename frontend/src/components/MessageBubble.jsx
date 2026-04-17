import { useState } from 'react'
import CodeBlock from './CodeBlock.jsx'

// ── Step metadata ──────────────────────────────────────────────────────────

const META = {
  Think: {
    label: 'Think',
    icon: '💭',
    color: '#9f7aea',
    bg: '#1a1730',
    border: '#44337a',
  },
  Act: {
    label: 'Act',
    icon: '⚡',
    color: '#f6ad55',
    bg: '#1a1200',
    border: '#7b4f00',
  },
  Observe: {
    label: 'Observe',
    icon: '👁',
    color: '#63b3ed',
    bg: '#0d1a2d',
    border: '#2c5282',
  },
}

// ── Step card header ───────────────────────────────────────────────────────

function StepHeader({ meta, badge }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      padding: '6px 12px',
      borderBottom: `1px solid ${meta.border}`,
      background: `${meta.bg}dd`,
    }}>
      <span style={{ fontSize: 13 }}>{meta.icon}</span>
      <span style={{
        fontSize: 11, fontWeight: 700, color: meta.color,
        fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '0.08em',
      }}>
        {meta.label}
      </span>
      {badge && (
        <span style={{
          marginLeft: 4,
          background: '#2d3748',
          color: '#a0aec0',
          borderRadius: 4,
          padding: '1px 8px',
          fontSize: 11,
          fontFamily: 'monospace',
        }}>
          {badge}
        </span>
      )}
    </div>
  )
}

// ── Think card ─────────────────────────────────────────────────────────────

function ThinkCard({ event }) {
  const meta = META.Think
  return (
    <div style={{ background: meta.bg, border: `1px solid ${meta.border}`, borderRadius: 8, overflow: 'hidden' }}>
      <StepHeader meta={meta} />
      <div style={{
        padding: '10px 14px',
        color: '#c4b5fd',
        fontSize: 13,
        lineHeight: 1.75,
        whiteSpace: 'pre-wrap',
      }}>
        {event.content}
      </div>
    </div>
  )
}

// ── Tool output parser ─────────────────────────────────────────────────────

/**
 * Split a raw tool-output string into { stdout, stderr }.
 * Handles literal \n escape sequences and common "Stdout:/Stderr:" prefixes
 * emitted by code interpreter tools.
 */
function parseToolOutput(raw) {
  // Normalise escaped newlines and tabs that arrive as literal characters
  const text = raw.replace(/\\n/g, '\n').replace(/\\t/g, '\t')

  // Pattern 1: explicit "Stdout:" / "Stderr:" sections
  const stdoutMatch = text.match(/^Stdout:\n?([\s\S]*?)(?=\nStderr:|\nError:|$)/m)
  const stderrMatch = text.match(/(?:^|\n)(?:Stderr|Error):\n?([\s\S]*)$/m)
  if (stdoutMatch || stderrMatch) {
    return {
      stdout: stdoutMatch ? stdoutMatch[1].trimEnd() : '',
      stderr: stderrMatch ? stderrMatch[1].trimEnd() : '',
    }
  }

  // Pattern 2: looks like a Python traceback / exception
  if (/Traceback \(most recent call last\)|^\w*Error:/m.test(text)) {
    return { stdout: '', stderr: text.trimEnd() }
  }

  // Default: everything is stdout
  return { stdout: text.trimEnd(), stderr: '' }
}

function ToolOutput({ raw }) {
  const { stdout, stderr } = parseToolOutput(raw)
  const obsMeta = META.Observe

  return (
    <div style={{
      background: obsMeta.bg,
      border: `1px solid ${obsMeta.border}`,
      borderRadius: 6,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '4px 10px',
        borderBottom: `1px solid ${obsMeta.border}`,
      }}>
        <span style={{ fontSize: 11 }}>{obsMeta.icon}</span>
        <span style={{
          fontSize: 10, fontWeight: 700, color: obsMeta.color,
          fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '0.08em',
        }}>
          {obsMeta.label}
        </span>
      </div>

      {/* Stdout */}
      {stdout && (
        <pre style={{
          margin: 0,
          padding: '8px 12px',
          fontFamily: 'monospace',
          fontSize: 12,
          color: '#90cdf4',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: 260,
          overflowY: 'auto',
          lineHeight: 1.6,
          borderBottom: stderr ? '1px solid #2c5282' : 'none',
        }}>
          {stdout}
        </pre>
      )}

      {/* Stderr */}
      {stderr && (
        <div>
          <div style={{
            padding: '3px 12px',
            fontSize: 10,
            fontFamily: 'monospace',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: '#fc8181',
            background: '#2d1515',
            borderTop: stdout ? '1px solid #c53030' : 'none',
            borderBottom: '1px solid #c53030',
          }}>
            stderr
          </div>
          <pre style={{
            margin: 0,
            padding: '8px 12px',
            fontFamily: 'monospace',
            fontSize: 12,
            color: '#fc8181',
            background: '#1a0a0a',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            maxHeight: 260,
            overflowY: 'auto',
            lineHeight: 1.6,
          }}>
            {stderr}
          </pre>
        </div>
      )}
    </div>
  )
}

// ── Pulsing dots loading indicator ────────────────────────────────────────

function PulsingDots({ color = '#718096' }) {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 5, height: 5, borderRadius: '50%', background: color,
          display: 'inline-block',
          animation: `dotPulse 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
    </span>
  )
}

// ── Act card (with embedded Observe for tool output) ───────────────────────

function ActCard({ event }) {
  const meta = META.Act
  const tools = event.tools || []
  // All code blocks start open
  const [openCode, setOpenCode] = useState(() =>
    Object.fromEntries(tools.map((_, i) => [i, true]))
  )

  const toggleCode = (i) => setOpenCode(prev => ({ ...prev, [i]: !prev[i] }))

  return (
    <div style={{ background: meta.bg, border: `1px solid ${meta.border}`, borderRadius: 8, overflow: 'hidden' }}>
      <StepHeader meta={meta} badge={tools[0]?.toolname} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '12px 14px' }}>
        {tools.map((tool, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

            {/* Tool input: code */}
            {tool.queryparams?.code && (
              <div>
                <button
                  onClick={() => toggleCode(i)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: '#a0aec0', fontSize: 11, fontFamily: 'monospace',
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    padding: '2px 0', marginBottom: openCode[i] ? 6 : 0,
                  }}
                >
                  <span style={{
                    display: 'inline-block',
                    transform: openCode[i] ? 'rotate(90deg)' : 'none',
                    transition: 'transform 0.15s',
                    fontSize: 9,
                  }}>
                    ▶
                  </span>
                  Code
                </button>
                {openCode[i] && <CodeBlock code={tool.queryparams.code} />}
              </div>
            )}

            {/* Non-code queryparams */}
            {tool.queryparams && !tool.queryparams.code && (
              <div>
                <div style={{ fontSize: 10, color: '#718096', fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                  params
                </div>
                <div style={{
                  background: '#0d1117', border: '1px solid #2d3748', borderRadius: 6,
                  padding: '8px 12px', fontFamily: 'monospace', fontSize: 12,
                  color: '#e2e8f0', whiteSpace: 'pre-wrap', maxHeight: 120, overflowY: 'auto',
                }}>
                  {typeof tool.queryparams === 'string'
                    ? tool.queryparams
                    : JSON.stringify(tool.queryparams, null, 2)}
                </div>
              </div>
            )}

            {/* Observe: tool output or pending indicator */}
            {tool.output
              ? <ToolOutput raw={tool.output} />
              : (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 10px',
                  background: META.Observe.bg,
                  border: `1px solid ${META.Observe.border}`,
                  borderRadius: 6,
                  fontSize: 11, color: META.Observe.color, fontFamily: 'monospace',
                }}>
                  <PulsingDots color={META.Observe.color} />
                  <span>running…</span>
                </div>
              )
            }
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Agent reasoning trace ──────────────────────────────────────────────────

function AgentTrace({ events }) {
  const [open, setOpen] = useState(true)

  if (!events || events.length === 0) return null

  const thinkCount = events.filter(e => e.current_label === 'Think').length
  const actCount = events.filter(e => e.current_label === 'Act').length

  return (
    <div style={{ maxWidth: '90%', width: '100%' }}>
      {/* Toggle */}
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'none', border: '1px solid #2d3748', borderRadius: 8,
          padding: '6px 12px', cursor: 'pointer', color: '#718096',
          fontSize: 12, fontFamily: 'monospace',
          marginBottom: open ? 10 : 0,
          transition: 'border-color 0.15s, color 0.15s',
          width: '100%', textAlign: 'left',
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = '#4a5568'; e.currentTarget.style.color = '#a0aec0' }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = '#2d3748'; e.currentTarget.style.color = '#718096' }}
      >
        <span style={{ display: 'inline-block', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s', fontSize: 9 }}>▶</span>
        <span>Reasoning trace</span>
        <span style={{ display: 'flex', gap: 6, marginLeft: 6 }}>
          {thinkCount > 0 && (
            <span style={{
              background: META.Think.bg, border: `1px solid ${META.Think.border}`,
              color: META.Think.color, borderRadius: 4, padding: '1px 6px', fontSize: 10,
            }}>
              {META.Think.icon} Think ×{thinkCount}
            </span>
          )}
          {actCount > 0 && (
            <span style={{
              background: META.Act.bg, border: `1px solid ${META.Act.border}`,
              color: META.Act.color, borderRadius: 4, padding: '1px 6px', fontSize: 10,
            }}>
              {META.Act.icon} Act ×{actCount}
            </span>
          )}
        </span>
      </button>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {events.map((event, idx) => {
            if (event.current_label === 'Think') return <ThinkCard key={idx} event={event} />
            if (event.current_label === 'Act') return <ActCard key={idx} event={event} />
            return null
          })}
        </div>
      )}
    </div>
  )
}

// ── Charts ─────────────────────────────────────────────────────────────────

const BACKEND = import.meta.env.VITE_API_URL || ''

function Charts({ urls }) {
  if (!urls || urls.length === 0) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: '90%' }}>
      {urls.map((url, i) => (
        <img
          key={i}
          src={`${BACKEND}${url}`}
          alt={`Chart ${i + 1}`}
          style={{
            borderRadius: 10,
            border: '1px solid #2d3748',
            maxWidth: '100%',
            display: 'block',
          }}
        />
      ))}
    </div>
  )
}

// ── Summary ────────────────────────────────────────────────────────────────

function Summary({ text }) {
  if (!text) return null
  return (
    <div style={{
      background: '#1e2533',
      border: '1px solid #2d3748',
      color: '#e2e8f0',
      padding: '12px 16px',
      borderRadius: '14px 14px 14px 4px',
      fontSize: 14,
      lineHeight: 1.75,
      maxWidth: '90%',
      whiteSpace: 'pre-wrap',
    }}>
      {text}
    </div>
  )
}

// ── MessageBubble ──────────────────────────────────────────────────────────

const wrap = (role) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: role === 'user' ? 'flex-end' : 'flex-start',
  gap: 8,
  maxWidth: '100%',
})

export default function MessageBubble({ message }) {
  const { role, content, result, streaming } = message

  if (role === 'user') {
    return (
      <div style={wrap('user')}>
        <div style={{
          background: '#1D9E75', color: 'white',
          padding: '10px 14px', borderRadius: '14px 14px 4px 14px',
          fontSize: 14, lineHeight: 1.6, maxWidth: '80%', whiteSpace: 'pre-wrap',
        }}>
          {content}
        </div>
      </div>
    )
  }

  // Assistant — plain text (error fallback, no result)
  if (!result) {
    return (
      <div style={wrap('assistant')}>
        <div style={{
          background: '#1e2533', border: '1px solid #2d3748', color: '#e2e8f0',
          padding: '10px 14px', borderRadius: '14px 14px 14px 4px',
          fontSize: 14, lineHeight: 1.7, maxWidth: '90%', whiteSpace: 'pre-wrap',
        }}>
          {content}
        </div>
      </div>
    )
  }

  const { events, summary, error, charts } = result

  return (
    <div style={wrap('assistant')}>
      {/* Initial waiting state before first event arrives */}
      {streaming && events.length === 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          color: '#718096', fontSize: 12, fontFamily: 'monospace',
          padding: '6px 2px',
        }}>
          <PulsingDots />
          <span>Agent is thinking…</span>
        </div>
      )}

      {/* 1. Reasoning trace */}
      <AgentTrace events={events} />

      {/* Pulsing indicator while agent is still working (after first event) */}
      {streaming && events.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          color: '#718096', fontSize: 12, fontFamily: 'monospace',
          padding: '6px 2px',
        }}>
          <PulsingDots />
          <span>Generating final response…</span>
        </div>
      )}

      {/* 2. Error (if any) */}
      {error && (
        <div style={{
          background: '#2d1515', border: '1px solid #c53030', borderRadius: 8,
          padding: '10px 14px', fontFamily: 'monospace', fontSize: 12,
          color: '#fc8181', whiteSpace: 'pre-wrap', maxWidth: '90%',
        }}>
          {error}
        </div>
      )}

      {/* 3. Charts */}
      <Charts urls={charts} />

      {/* 4. Summary */}
      <Summary text={summary} />
    </div>
  )
}
