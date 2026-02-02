import React, { useState, useRef } from "react"

// Upload component: handles PDF selection and upload, polls job status,
// and sends chat prompts (including employee_id when available).
export default function Upload({ onNewMessage }) {
  const [file, setFile] = useState(null)
  const [prompt, setPrompt] = useState("")
  const [status, setStatus] = useState("")
  const [employeeId, setEmployeeId] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [sessionId, setSessionId] = useState(null)  // For conversation memory
  const abortControllerRef = useRef(null)  // For canceling requests
  const requestStartTimeRef = useRef(null)  // For tracking response time
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
  // Accepts optional fileToUpload parameter for when file state is cleared before upload
  async function uploadAndWait(fileToUpload = null) {
    const uploadFile = fileToUpload || file
    if (!uploadFile) return null
    setIsProcessing(true)

    // Create abort controller for this request
    abortControllerRef.current = new AbortController()
    const signal = abortControllerRef.current.signal
    const uploadStartTime = Date.now()  // Start timing for upload

    try {
      const fd = new FormData()
      fd.append("file", uploadFile)
      setStatus("Uploading (auto)...")
      // Discover a working backend host before uploading
      const base = await findBackendBase()
      if (!base) {
        onNewMessage({ type: "error", text: `Upload aborted: cannot reach backend on port 8000 (tried several hosts).` })
        setStatus("Backend unreachable")
        setIsProcessing(false)
        return null
      }
      const res = await fetch(`${base}/api/upload-cv`, { method: "POST", body: fd, signal })
      const json = await res.json()
      onNewMessage({ type: "info", text: `Uploaded ${uploadFile.name} — job ${json.job_id}` })
      const jid = json.job_id
      setStatus("Processing CV with LLM (this may take a while)...")

      // Poll indefinitely until job completes - no timeout limit
      let pollCount = 0
      while (true) {
        // Check if aborted
        if (signal.aborted) {
          return null
        }
        try {
          const s = await fetch(`${base}/api/job/${jid}`, { signal })
          if (s.ok) {
            const j = await s.json()
            if (j.status === "done" && j.employee_id) {
              const processingTime = ((Date.now() - uploadStartTime) / 1000).toFixed(1)
              setEmployeeId(j.employee_id)
              onNewMessage({ type: "info", text: `Processing finished — employee id ${j.employee_id} (${processingTime}s)` })
              setStatus(`Processed (employee ${j.employee_id}) in ${processingTime}s`)
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
        pollCount++
        // Update status every 10 polls (~10 seconds) to show progress
        if (pollCount % 10 === 0) {
          setStatus(`Processing CV with LLM... (${pollCount}s elapsed)`)
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
    } catch (err) {
      // Check if it was aborted by user
      if (err.name === 'AbortError') {
        return null  // Already handled by handleStop
      }
      // Provide a clearer hint when the fetch fails (network/backend unreachable)
      onNewMessage({ type: "error", text: `Upload failed: ${err.message}. Is the backend running at http://${window.location.hostname}:8000 ?` })
      setIsProcessing(false)
      return null
    }
  }

  // Clear the selected file
  function clearFile() {
    setFile(null)
    // Reset the file input
    const fileInput = document.getElementById('file-input')
    if (fileInput) fileInput.value = ''
  }

  // Stop the current request
  function handleStop() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsProcessing(false)
    setStatus("Stopped by user")
    onNewMessage({ type: "info", text: "Request stopped by user" })
  }

  async function handleChat(e) {
    e.preventDefault()

    // Allow submission if there's a prompt OR if there's a file to process
    // Note: Allow file upload even if employeeId exists (user can switch candidates)
    const hasFile = file && !isProcessing
    if (!prompt && !hasFile) return

    const currentPrompt = prompt
    const currentFile = file
    setPrompt("")  // Clear input immediately

    try {
      // If a file is selected and not yet processed, upload it first
      if (hasFile) {
        // Show the attachment in chat history when submitting
        onNewMessage({ type: "attachment", filename: currentFile.name })
        clearFile()  // Clear the preview

        const newEmployeeId = await uploadAndWait(currentFile)

        // If no prompt was provided, just show success message and return
        if (!currentPrompt) {
          if (newEmployeeId) {
            onNewMessage({ type: "assistant", text: `Resume processed successfully! Employee ID: ${newEmployeeId}. You can now ask questions about this candidate.` })
          }
          return
        }
      }

      // If there's a prompt, continue with chat
      if (currentPrompt) {
        setIsProcessing(true)
        setStatus("Sending prompt...")
        requestStartTimeRef.current = Date.now()  // Start timing
        onNewMessage({ type: "user", text: currentPrompt })

        // Create abort controller for chat request
        abortControllerRef.current = new AbortController()
        const signal = abortControllerRef.current.signal

        const base = await findBackendBase()
        if (!base) {
          onNewMessage({ type: "error", text: `Cannot reach backend for chat: tried several hosts on port 8000.` })
          setStatus("Backend unreachable")
          setIsProcessing(false)
          return
        }
        const res = await fetch(`${base}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: currentPrompt,
            employee_id: employeeId,
            session_id: sessionId  // Send session_id for conversation memory
          }),
          signal
        })

        if (!res.ok) {
          let errText = null
          try {
            const errJson = await res.json()
            errText = errJson.detail || errJson.error || JSON.stringify(errJson)
          } catch (err) {
            errText = await res.text()
          }
          setStatus("Error from server")
          onNewMessage({ type: "error", text: `Error: ${errText}` })
          setIsProcessing(false)
          return
        }

        const json = await res.json()

        // Calculate response time
        const responseTime = requestStartTimeRef.current
          ? ((Date.now() - requestStartTimeRef.current) / 1000).toFixed(2)
          : null
        requestStartTimeRef.current = null

        setStatus(responseTime ? `Reply received in ${responseTime}s` : "Reply received")
        setIsProcessing(false)

        // Store session_id for conversation continuity
        if (json.session_id) {
          setSessionId(json.session_id)
        }

        // Store employee_id if found (from name search or original upload)
        if (json.employee_id && !employeeId) {
          setEmployeeId(json.employee_id)
          console.log(`Found employee by name search: ${json.employee_name} (ID: ${json.employee_id})`)
        }

        onNewMessage({ type: "assistant", text: json.reply, responseTime })
      }
    } catch (err) {
      // Check if it was aborted by user
      if (err.name === 'AbortError') {
        return  // Already handled by handleStop
      }
      setStatus("Network error")
      setIsProcessing(false)
      onNewMessage({ type: "error", text: `Network error: ${err.message}. Is the backend running at http://${window.location.hostname}:8000 ?` })
    }
  }

  return (
    <div className="upload">
      {/* File preview above input - shown when file is selected but not yet submitted */}
      {file && !isProcessing && (
        <div className="file-preview">
          <div className="file-preview-content">
            <span className="file-icon">📄</span>
            <span className="file-name">{file.name}</span>
            <button
              type="button"
              className="file-remove-btn"
              onClick={clearFile}
              title="Remove file"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleChat} className="chat-input-container">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => {
            const selectedFile = e.target.files[0]
            setFile(selectedFile)
            // File preview is shown above input, not in chat history
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
          placeholder={isProcessing ? "Waiting for response..." : "Ask anything"}
          className="prompt-input"
          disabled={isProcessing}
        />
        {isProcessing ? (
          <button type="button" className="stop-btn" onClick={handleStop} title="Stop">
            <span className="stop-icon">■</span>
          </button>
        ) : (
          <button type="submit" className="send-btn">
            Send
          </button>
        )}
      </form>
      {status && <div className="status">{status}</div>}
    </div>
  )
}
