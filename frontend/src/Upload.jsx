import React, { useState } from "react"

export default function Upload({ onNewMessage }) {
  const [file, setFile] = useState(null)
  const [prompt, setPrompt] = useState("")
  const [status, setStatus] = useState("")
  const [employeeId, setEmployeeId] = useState(null)

  async function handleUpload(e) {
    e.preventDefault()
    if (!file) return
    const fd = new FormData()
    fd.append("file", file)
    setStatus("Uploading...")
    const res = await fetch("http://localhost:8000/api/upload-cv", { method: "POST", body: fd })
    const json = await res.json()
    setStatus(`Queued (${json.job_id})`)
    onNewMessage({ type: "info", text: `Uploaded ${file.name} — job ${json.job_id}` })
    // poll job status until it's done and returns an employee_id
    (async function poll() {
      const jid = json.job_id
      const start = Date.now()
      while (Date.now() - start < 60_000) {
        try {
          const s = await fetch(`http://localhost:8000/api/job/${jid}`)
          if (s.ok) {
            const j = await s.json()
            if (j.status === "done" && j.employee_id) {
              setEmployeeId(j.employee_id)
              onNewMessage({ type: "info", text: `Processing finished — employee id ${j.employee_id}` })
              setStatus(`Processed (employee ${j.employee_id})`)
              return
            }
            if (j.status === "failed") {
              onNewMessage({ type: "error", text: `Processing failed: ${j.reason || JSON.stringify(j)}` })
              setStatus("Processing failed")
              return
            }
          }
        } catch (err) {
          // ignore transient errors
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
      onNewMessage({ type: "error", text: "Processing timed out (no result within 60s)" })
      setStatus("Timed out")
    })()
  }

  async function handleChat(e) {
    e.preventDefault()
    if (!prompt) return
    setStatus("Sending prompt...")
    try {
      // show the user's prompt above the reply in the UI
      onNewMessage({ type: "user", text: prompt })
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, employee_id: employeeId }),
      })

      if (!res.ok) {
        // try to parse JSON error from server
        let errText = null
        try {
          const errJson = await res.json()
          errText = errJson.detail || errJson.error || JSON.stringify(errJson)
        } catch (e) {
          errText = await res.text()
        }
        setStatus("Error from server")
        onNewMessage({ type: "error", text: `Error: ${errText}` })
        return
      }

      const json = await res.json()
      setStatus("Reply received")
      onNewMessage({ type: "assistant", text: json.reply })
    } catch (e) {
      setStatus("Network error")
      onNewMessage({ type: "error", text: `Network error: ${e.message}` })
    }
  }

  return (
    <div className="upload">
      <form onSubmit={handleUpload}>
        <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} />
        <button type="submit">Upload CV</button>
      </form>

      <form onSubmit={handleChat}>
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Ask about the CV or give an instruction" />
        <button type="submit">Send</button>
      </form>
      <div className="status">{status}</div>
    </div>
  )
}
