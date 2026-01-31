import React, { useState } from "react"

// NLCrud component: simple UI to send a natural-language CRUD command to the backend,
// display the parsed proposal, and confirm/apply it. It calls `/api/nl-command`
// and `/api/nl/{id}/confirm`.
export default function NLCrud({ onNewMessage }) {
  const [command, setCommand] = useState("")
  const [pendingId, setPendingId] = useState(null)
  const [proposal, setProposal] = useState(null)

  async function sendCommand(e) {
    e && e.preventDefault()
    if (!command) return
    onNewMessage({ type: "info", text: `Sending NL command: ${command}` })
    try {
      const res = await fetch("http://localhost:8000/api/nl-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command }),
      })
      const j = await res.json()
      if (!res.ok) {
        onNewMessage({ type: "error", text: `NL parse error: ${j.detail || JSON.stringify(j)}` })
        return
      }
      setPendingId(j.pending_id)
      setProposal(j.proposal)
      onNewMessage({ type: "info", text: `Proposal received — pending ${j.pending_id}` })
    } catch (err) {
      onNewMessage({ type: "error", text: `Network error: ${err.message}` })
    }
  }

  async function confirm() {
    if (!pendingId) return
    try {
      const res = await fetch(`http://localhost:8000/api/nl/${pendingId}/confirm`, { method: "POST", headers: { "Content-Type": "application/json" } })
      const j = await res.json()
      if (!res.ok) {
        onNewMessage({ type: "error", text: `Confirm error: ${j.detail || JSON.stringify(j)}` })
        return
      }
      onNewMessage({ type: "info", text: `Confirmed: ${JSON.stringify(j)}` })
      // clear
      setPendingId(null)
      setProposal(null)
      setCommand("")
      try { localStorage.removeItem('global_prompt') } catch (e) {}
    } catch (err) {
      onNewMessage({ type: "error", text: `Network error: ${err.message}` })
    }
  }

  // Hide the Parse button if a global prompt exists (user typed in main input). This
  // matches the merged UI behavior where Send handles upload/parse when prompt is used.
  let globalPrompt = null
  try {
    globalPrompt = localStorage.getItem('global_prompt')
  } catch (err) {
    globalPrompt = null
  }

  return (
    <div style={{ marginTop: 12 }}>
      <form onSubmit={sendCommand}>
        <input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="Natural language CRUD (e.g. update employee 3 email to x@x.com)" style={{ width: '70%' }} />
        {!globalPrompt && <button type="submit">Parse</button>}
      </form>

      {proposal && (
        <div style={{ marginTop: 8 }}>
          <div><strong>Proposal</strong></div>
          <pre style={{ background: '#f2f2f2', padding: 8 }}>{JSON.stringify(proposal, null, 2)}</pre>
          <button onClick={confirm}>Confirm and Apply</button>
        </div>
      )}
    </div>
  )
}
