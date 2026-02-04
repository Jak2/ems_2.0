import React, { useState, useRef } from "react"

// Upload component: handles PDF selection and upload, polls job status,
// and sends chat prompts (including employee_id when available).
export default function Upload({ onNewMessage, onLoadingChange }) {
  const [files, setFiles] = useState([])  // Changed to array for multiple files
  const [prompt, setPrompt] = useState("")
  const [status, setStatus] = useState("")
  const [employeeId, setEmployeeId] = useState(null)
  const [isProcessingState, setIsProcessingState] = useState(false)
  const [sessionId, setSessionId] = useState(null)  // For conversation memory
  const abortControllerRef = useRef(null)  // For canceling requests
  const requestStartTimeRef = useRef(null)  // For tracking response time
  const textareaRef = useRef(null)  // For auto-resize textarea

  // Wrapper to update both local state and parent loading bar state
  const setIsProcessing = (value) => {
    setIsProcessingState(value)
    if (onLoadingChange) onLoadingChange(value)
  }
  const isProcessing = isProcessingState
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

  // Upload a single file and wait for processing to finish.
  // Returns employee_id or null on failure/timeout.
  async function uploadSingleFile(uploadFile, base, signal, fileIndex = 0, totalFiles = 1) {
    try {
      const fd = new FormData()
      fd.append("file", uploadFile)
      const fileLabel = totalFiles > 1 ? ` (${fileIndex + 1}/${totalFiles})` : ""
      setStatus(`Uploading${fileLabel}...`)

      const res = await fetch(`${base}/api/upload-cv`, { method: "POST", body: fd, signal })
      const json = await res.json()
      onNewMessage({ type: "info", text: `Uploaded ${uploadFile.name} — job ${json.job_id}` })
      const jid = json.job_id
      setStatus(`Processing CV${fileLabel} with LLM...`)

      // Poll until job completes
      let pollCount = 0
      while (true) {
        if (signal.aborted) return null
        try {
          const s = await fetch(`${base}/api/job/${jid}`, { signal })
          if (s.ok) {
            const j = await s.json()
            if (j.status === "done" && j.employee_id) {
              onNewMessage({ type: "info", text: `CV processed — employee id ${j.employee_id}` })
              return j.employee_id
            }
            if (j.status === "failed") {
              onNewMessage({ type: "error", text: `Processing failed for ${uploadFile.name}: ${j.reason || JSON.stringify(j)}` })
              return null
            }
          }
        } catch (err) {
          // ignore transient errors while polling
        }
        pollCount++
        if (pollCount % 10 === 0) {
          setStatus(`Processing CV${fileLabel}... (${pollCount}s elapsed)`)
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
    } catch (err) {
      if (err.name === 'AbortError') return null
      onNewMessage({ type: "error", text: `Upload failed for ${uploadFile.name}: ${err.message}` })
      return null
    }
  }

  // Upload multiple files sequentially and wait for all to finish.
  // Returns array of employee_ids or empty array on failure.
  async function uploadAndWait(filesToUpload = null) {
    const uploadFiles = filesToUpload || files
    if (!uploadFiles || uploadFiles.length === 0) return []
    setIsProcessing(true)

    // Create abort controller for this request
    abortControllerRef.current = new AbortController()
    const signal = abortControllerRef.current.signal

    // Discover a working backend host before uploading
    const base = await findBackendBase()
    if (!base) {
      onNewMessage({ type: "error", text: `Upload aborted: cannot reach backend on port 8000 (tried several hosts).` })
      setStatus("Backend unreachable")
      setIsProcessing(false)
      return []
    }

    const employeeIds = []
    for (let i = 0; i < uploadFiles.length; i++) {
      if (signal.aborted) break
      const empId = await uploadSingleFile(uploadFiles[i], base, signal, i, uploadFiles.length)
      if (empId) {
        employeeIds.push(empId)
        setEmployeeId(empId)  // Set to most recent
      }
    }

    if (employeeIds.length > 0) {
      setStatus(`Processed ${employeeIds.length} resume(s)`)
    } else {
      setStatus("Processing complete")
    }
    setIsProcessing(false)
    return employeeIds
  }

  // Clear all selected files
  function clearFiles() {
    setFiles([])
    // Reset the file input
    const fileInput = document.getElementById('file-input')
    if (fileInput) fileInput.value = ''
  }

  // Remove a specific file from the list
  function removeFile(index) {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  // Handle textarea auto-resize
  function handleTextareaResize(e) {
    const textarea = e.target
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px'
  }

  // Handle keyboard events for Shift+Enter (new line) vs Enter (submit)
  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      // Trigger form submit
      const form = e.target.closest('form')
      if (form) form.requestSubmit()
    }
    // Shift+Enter allows default behavior (new line)
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

    // Allow submission if there's a prompt OR if there are files to process
    // Note: Allow file upload even if employeeId exists (user can switch candidates)
    const hasFiles = files.length > 0 && !isProcessing
    if (!prompt && !hasFiles) return

    const currentPrompt = prompt
    const currentFiles = [...files]  // Copy array
    setPrompt("")  // Clear input immediately

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    // Start timing from when user hits Send - captures entire request duration
    requestStartTimeRef.current = Date.now()

    try {
      // If files are selected and not yet processed, upload them first
      if (hasFiles) {
        // Show the attachments in chat history when submitting
        const fileNames = currentFiles.map(f => f.name).join(', ')
        onNewMessage({ type: "attachment", filename: currentFiles.length > 1 ? `${currentFiles.length} files: ${fileNames}` : currentFiles[0].name })
        clearFiles()  // Clear the preview

        const employeeIds = await uploadAndWait(currentFiles)

        // If no prompt was provided, show success message with total time and return
        if (!currentPrompt) {
          const totalTime = requestStartTimeRef.current
            ? ((Date.now() - requestStartTimeRef.current) / 1000).toFixed(2)
            : null
          requestStartTimeRef.current = null
          if (employeeIds.length > 0) {
            const msg = employeeIds.length > 1
              ? `${employeeIds.length} resumes processed successfully! Employee IDs: ${employeeIds.join(', ')}. You can now ask questions about these candidates.`
              : `Resume processed successfully! Employee ID: ${employeeIds[0]}. You can now ask questions about this candidate.`
            onNewMessage({
              type: "assistant",
              text: msg,
              responseTime: totalTime
            })
          }
          return
        }
      }

      // If there's a prompt, continue with chat
      if (currentPrompt) {
        setIsProcessing(true)
        setStatus("Sending prompt...")
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
      {/* File preview above input - shown when files are selected but not yet submitted */}
      {files.length > 0 && !isProcessing && (
        <div className="file-preview">
          {files.map((f, index) => (
            <div key={index} className="file-preview-content">
              <span className="file-icon">📄</span>
              <span className="file-name">{f.name}</span>
              <button
                type="button"
                className="file-remove-btn"
                onClick={() => removeFile(index)}
                title="Remove file"
              >
                ✕
              </button>
            </div>
          ))}
          {files.length > 1 && (
            <button
              type="button"
              className="clear-all-btn"
              onClick={clearFiles}
              title="Clear all files"
            >
              Clear all ({files.length})
            </button>
          )}
        </div>
      )}

      <form onSubmit={handleChat} className="chat-input-container">
        <input
          type="file"
          accept="application/pdf"
          multiple
          onChange={(e) => {
            const selectedFiles = Array.from(e.target.files)
            setFiles(prev => [...prev, ...selectedFiles])
            // Reset input so same file can be selected again
            e.target.value = ''
          }}
          id="file-input"
          style={{ display: 'none' }}
        />
        <label htmlFor="file-input" className="file-picker-btn" title="Attach PDFs (multiple allowed)">
          <span className="plus-icon">+</span>
        </label>

        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={(e) => {
            const v = e.target.value
            setPrompt(v)
            handleTextareaResize(e)
            try {
              if (v && v.trim() !== "") localStorage.setItem('global_prompt', v)
              else localStorage.removeItem('global_prompt')
            } catch (err) {
              // ignore storage errors
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder={isProcessing ? "Waiting for response..." : "Ask anything (Shift+Enter for new line)"}
          className="prompt-input"
          disabled={isProcessing}
          rows={1}
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
