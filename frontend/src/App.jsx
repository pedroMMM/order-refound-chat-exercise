import { useState, useRef, useEffect } from 'react'

const C = {
  bg: '#0f0f0f',
  panel: '#111',
  border: '#1e1e1e',
  node: { llm: '#6366f1', tools: '#f59e0b', phone_validation: '#10b981', END: '#555', start: '#3b82f6' },
  event: { tool_call: '#f59e0b', tool_result: '#10b981', system: '#6366f1', routing: '#3b82f6', llm_reasoning: '#a855f7', node_start: '#334155', node_end: '#1e293b', session_state: '#0891b2' },
}

const s = {
  root: { display: 'flex', width: '100%', height: '100vh', fontFamily: 'system-ui, sans-serif', background: C.bg, color: '#e0e0e0' },
  chat: { flex: 1, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${C.border}` },
  admin: { width: 480, display: 'flex', flexDirection: 'column', background: C.panel, overflow: 'hidden' },
  header: { padding: '10px 14px', borderBottom: `1px solid ${C.border}`, fontSize: 12, fontWeight: 600, color: '#666', display: 'flex', alignItems: 'center', gap: 8 },
  msgs: { flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 },
  inputRow: { padding: 10, borderTop: `1px solid ${C.border}`, display: 'flex', gap: 8 },
  input: { flex: 1, background: '#1a1a1a', border: `1px solid #2a2a2a`, color: '#e0e0e0', borderRadius: 6, padding: '8px 12px', fontSize: 13, outline: 'none' },
  btn: { background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 14px', cursor: 'pointer', fontSize: 13 },
  adminScroll: { flex: 1, overflowY: 'auto', padding: 10, display: 'flex', flexDirection: 'column', gap: 6 },
  tag: (color) => ({ fontSize: 10, color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }),
  pill: (color) => ({ display: 'inline-block', background: color + '22', color, border: `1px solid ${color}44`, borderRadius: 4, padding: '1px 6px', fontSize: 10, fontWeight: 700 }),
  pre: { fontSize: 11, color: '#9ca3af', whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: '4px 0 0', fontFamily: 'monospace' },
  mono: { fontSize: 11, fontFamily: 'monospace', color: '#6b7280' },
}

function Message({ role, content }) {
  const user = role === 'user'
  return (
    <div style={{ alignSelf: user ? 'flex-end' : 'flex-start', maxWidth: '78%' }}>
      <div style={{ background: user ? '#2563eb' : '#1e1e1e', border: user ? 'none' : `1px solid ${C.border}`, borderRadius: 10, padding: '8px 12px', fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
        {content}
      </div>
    </div>
  )
}

function Card({ color, title, children, compact }) {
  return (
    <div style={{ background: '#161616', border: `1px solid ${color}33`, borderLeft: `3px solid ${color}`, borderRadius: 6, padding: compact ? '6px 8px' : '8px 10px' }}>
      <div style={s.tag(color)}>{title}</div>
      {children}
    </div>
  )
}

function NodeFlow({ nodes }) {
  if (!nodes.length) return null
  return (
    <Card color='#334155' title='Execution Flow'>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6, alignItems: 'center' }}>
        <span style={s.pill('#3b82f6')}>START</span>
        {nodes.map((n, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: '#374151', fontSize: 10 }}>→</span>
            <span style={s.pill(C.node[n.node] || '#888')}>{n.node}{n.duration_ms != null ? ` ${n.duration_ms}ms` : ''}</span>
          </span>
        ))}
        <span style={{ color: '#374151', fontSize: 10 }}>→</span>
        <span style={s.pill('#555')}>END</span>
      </div>
    </Card>
  )
}

function SessionState({ data }) {
  return (
    <Card color='#0891b2' title='Session State'>
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '3px 10px', marginTop: 5 }}>
        {Object.entries(data).map(([k, v]) => (
          v != null && [
            <span key={k + 'k'} style={{ ...s.mono, color: '#4b5563' }}>{k}</span>,
            <span key={k + 'v'} style={{ ...s.mono, color: '#e0e0e0' }}>{String(v)}</span>,
          ]
        ))}
      </div>
    </Card>
  )
}

function RoutingCard({ event }) {
  return (
    <Card color={C.event.routing} title={`Routing · ${event.from} → ${event.to}`} compact>
      <div style={{ ...s.mono, marginTop: 3, color: '#9ca3af' }}>{event.reason}</div>
    </Card>
  )
}

function LLMReasoningCard({ event }) {
  return (
    <Card color={C.event.llm_reasoning} title='LLM Reasoning'>
      {event.content && <p style={s.pre}>{event.content}</p>}
      {event.tool_calls_planned?.length > 0 && (
        <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {event.tool_calls_planned.map((t, i) => <span key={i} style={s.pill('#f59e0b')}>{t}</span>)}
        </div>
      )}
    </Card>
  )
}

function ToolCallCard({ event }) {
  return (
    <Card color={C.event.tool_call} title={`Tool Call · ${event.name}`}>
      <pre style={s.pre}>{JSON.stringify(event.input, null, 2)}</pre>
    </Card>
  )
}

function ToolResultCard({ event }) {
  return (
    <Card color={C.event.tool_result} title={`Tool Result · ${event.name}`}>
      <pre style={s.pre}>{typeof event.output === 'string' ? event.output : JSON.stringify(event.output, null, 2)}</pre>
    </Card>
  )
}

function SystemCard({ event }) {
  return (
    <Card color={C.event.system} title={`System · ${event.name}`}>
      <pre style={s.pre}>{JSON.stringify(event.data, null, 2)}</pre>
    </Card>
  )
}

function TraceEvent({ event }) {
  if (event.type === 'routing') return <RoutingCard event={event} />
  if (event.type === 'llm_reasoning') return <LLMReasoningCard event={event} />
  if (event.type === 'tool_call') return <ToolCallCard event={event} />
  if (event.type === 'tool_result') return <ToolResultCard event={event} />
  if (event.type === 'system') return <SystemCard event={event} />
  return null
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [traceEvents, setTraceEvents] = useState([])
  const [nodeFlow, setNodeFlow] = useState([])
  const [sessionState, setSessionState] = useState(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const msgsEndRef = useRef(null)
  const traceEndRef = useRef(null)

  useEffect(() => { msgsEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => { traceEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [traceEvents, nodeFlow])

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages(m => [...m, { role: 'user', content: text }])
    setLoading(true)

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let assistantMsg = ''
      setMessages(m => [...m, { role: 'assistant', content: '' }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const lines = decoder.decode(value).split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let event
          try { event = JSON.parse(line.slice(6)) } catch { continue }

          if (event.type === 'token') {
            assistantMsg += event.content
            setMessages(m => { const u = [...m]; u[u.length - 1] = { role: 'assistant', content: assistantMsg }; return u })
          } else if (event.type === 'done') {
            if (event.session_id) setSessionId(event.session_id)
          } else if (event.type === 'node_start') {
            // will be paired with node_end
          } else if (event.type === 'node_end') {
            setNodeFlow(f => [...f, { node: event.node, duration_ms: event.duration_ms }])
          } else if (event.type === 'session_state') {
            setSessionState(event.data)
          } else if (['routing', 'llm_reasoning', 'tool_call', 'tool_result', 'system'].includes(event.type)) {
            setTraceEvents(t => [...t, event])
          }
        }
      }
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const visibleEvents = traceEvents.filter(e => ['routing', 'llm_reasoning', 'tool_call', 'tool_result', 'system'].includes(e.type))

  return (
    <div style={s.root}>
      {/* Chat */}
      <div style={s.chat}>
        <div style={s.header}>
          Customer Chat
          {sessionId && <span style={s.mono}>· {sessionId.slice(0, 8)}</span>}
        </div>
        <div style={s.msgs}>
          {messages.length === 0 && <div style={{ color: '#444', fontSize: 13, textAlign: 'center', marginTop: 60 }}>Send a message to start</div>}
          {messages.map((m, i) => <Message key={i} {...m} />)}
          {loading && messages[messages.length - 1]?.role !== 'assistant' && <div style={{ alignSelf: 'flex-start', color: '#444', fontSize: 12 }}>thinking…</div>}
          <div ref={msgsEndRef} />
        </div>
        <div style={s.inputRow}>
          <input style={s.input} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKey} placeholder="Type a message…" disabled={loading} />
          <button style={s.btn} onClick={send} disabled={loading}>Send</button>
        </div>
      </div>

      {/* Admin */}
      <div style={s.admin}>
        <div style={s.header}>
          Agent Trace
          {visibleEvents.length > 0 && (
            <button onClick={() => { setTraceEvents([]); setNodeFlow([]); setSessionState(null) }}
              style={{ marginLeft: 'auto', background: 'none', border: `1px solid ${C.border}`, color: '#555', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 10 }}>
              clear
            </button>
          )}
        </div>
        <div style={s.adminScroll}>
          {visibleEvents.length === 0 && nodeFlow.length === 0 && (
            <div style={{ color: '#333', fontSize: 12, textAlign: 'center', marginTop: 60 }}>
              Agent reasoning will appear here
            </div>
          )}

          {sessionState && <SessionState data={sessionState} />}
          {nodeFlow.length > 0 && <NodeFlow nodes={nodeFlow} />}

          {visibleEvents.map((e, i) => <TraceEvent key={i} event={e} />)}

          <div ref={traceEndRef} />
        </div>
      </div>
    </div>
  )
}
