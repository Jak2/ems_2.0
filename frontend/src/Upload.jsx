import React, { useState } from "react"

// Upload component: handles PDF selection and upload, polls job status,
// and sends chat prompts (including employee_id when available).
export default function Upload({ onNewMessage }) {
  const [file, setFile] = useState(null)
  const [prompt, setPrompt] = useState("")
  const [status, setStatus] = useState("")
  const [employeeId, setEmployeeId] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  // file selection is done via the input below; we no longer expose a separate
  // "Upload" button. The selected file will be uploaded automatically when the
  // user presses Send. This simplifies the UX as requested.

  // Try to discover a working backend base URL. We attempt a short GET /health
  // against a few likely hosts and return the first that responds.
  async function findBackendBase() {
    const hosts = [window.location.hostname, '127.0.0.1', 'localhost']
    for (const h of hosts) {
      const url = `http://${h}:8000/health`
      try {
        const controller = new AbortController()
        const id = setTimeout(() => controller.abort(), 3000)
        const r = await fetch(url, { method: 'GET', signal: controller.signal })
        clearTimeout(id)
        if (r.ok) return `http://${h}:8000`
      } catch (err) {
        // try next host
      }
    }
    return null
  }

  // Upload the selected file and wait for processing to finish.
  // Returns employee_id or null on failure/timeout.
  async function uploadAndWait() {
    if (!file) return null
    setIsProcessing(true)
    try {
      const fd = new FormData()
      fd.append("file", file)
      setStatus("Uploading (auto)...")
      // Discover a working backend host before uploading
      const base = await findBackendBase()
      if (!base) {
        onNewMessage({ type: "error", text: `Upload aborted: cannot reach backend on port 8000 (tried several hosts).` })
        setStatus("Backend unreachable")
        setIsProcessing(false)
        return null
      }
      const res = await fetch(`${base}/api/upload-cv`, { method: "POST", body: fd })
      const json = await res.json()
      onNewMessage({ type: "info", text: `Uploaded ${file.name} — job ${json.job_id}` })
      const jid = json.job_id
      const start = Date.now()
      while (Date.now() - start < 60_000) {
        try {
          const s = await fetch(`${base}/api/job/${jid}`)
          if (s.ok) {
            const j = await s.json()
            if (j.status === "done" && j.employee_id) {
              setEmployeeId(j.employee_id)
              onNewMessage({ type: "info", text: `Processing finished — employee id ${j.employee_id}` })
              setStatus(`Processed (employee ${j.employee_id})`)
              setIsProcessing(false)
              return j.employee_id
            }
            if (j.status === "failed") {
              onNewMessage({ type: "error", text: `Processing failed: ${j.reason || JSON.stringify(j)}` })
              setStatus("Processing failed")
              setIsProcessing(false)
              return null
            }
          }
        } catch (err) {
          // ignore transient errors while polling
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
      onNewMessage({ type: "error", text: "Processing timed out (no result within 60s)" })
      setStatus("Timed out")
      setIsProcessing(false)
      return null
    } catch (err) {
      // Provide a clearer hint when the fetch fails (network/backend unreachable)
      onNewMessage({ type: "error", text: `Upload failed: ${err.message}. Is the backend running at http://${window.location.hostname}:8000 ?` })
      setIsProcessing(false)
      return null
    }
  }

  async function handleChat(e) {
    e.preventDefault()
    if (!prompt) return
    
    const currentPrompt = prompt
    setStatus("Sending prompt...")
    
    // Clear the input box immediately after user hits enter
    setPrompt("")
    
    try {
      // show the user's prompt above the reply in the UI
      onNewMessage({ type: "user", text: currentPrompt })

      // If a file is selected and not yet processed, upload it first (merged behavior)
      if (file && !employeeId && !isProcessing) {
        await uploadAndWait()
      }

      const base = await findBackendBase()
      if (!base) {
        onNewMessage({ type: "error", text: `Cannot reach backend for chat: tried several hosts on port 8000.` })
        setStatus("Backend unreachable")
        return
      }
      const res = await fetch(`${base}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: currentPrompt, employee_id: employeeId }),
      })

      if (!res.ok) {
        // try to parse JSON error from server
        let errText = null
        try {
          const errJson = await res.json()
          errText = errJson.detail || errJson.error || JSON.stringify(errJson)
        } catch (err) {
          errText = await res.text()
        }
        setStatus("Error from server")
        onNewMessage({ type: "error", text: `Error: ${errText}` })
        return
      }

      const json = await res.json()
      setStatus("Reply received")
      onNewMessage({ type: "assistant", text: json.reply })
    } catch (err) {
      setStatus("Network error")
      onNewMessage({ type: "error", text: `Network error: ${err.message}. Is the backend running at http://${window.location.hostname}:8000 ?` })
    }
  }

  return (
    <div className="upload">
      <form onSubmit={handleChat} className="chat-input-container">
        <input 
          type="file" 
          accept="application/pdf" 
          onChange={(e) => {
            const selectedFile = e.target.files[0]
            setFile(selectedFile)
            // Show the attached file immediately as a message
            if (selectedFile) {
              onNewMessage({ type: "attachment", filename: selectedFile.name })
            }
          }}
          id="file-input"
          style={{ display: 'none' }}
        />
        <label htmlFor="file-input" className="file-picker-btn" title="Attach PDF">
          <span className="plus-icon">+</span>
        </label>
        
        <input 
          value={prompt} 
          onChange={(e) => {
            const v = e.target.value
            setPrompt(v)
            try {
              if (v && v.trim() !== "") localStorage.setItem('global_prompt', v)
              else localStorage.removeItem('global_prompt')
            } catch (err) {
              // ignore storage errors
            }
          }} 
          placeholder="Ask anything"
          className="prompt-input"
        />
        <button type="submit" className="send-btn" disabled={isProcessing}>
          {isProcessing ? "Processing..." : "Send"}
        </button>
      </form>
      {status && <div className="status">{status}</div>}
    </div>
  )
}
