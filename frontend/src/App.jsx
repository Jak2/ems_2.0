import React, { useState, useEffect, useRef } from "react"
import Upload from "./Upload"

// Main application component. Holds the global message list and renders
// the Upload and NL-CRUD components. Messages are displayed in the chat pane.

export default function App() {
  const [messages, setMessages] = useState([])
  const [dark, setDark] = useState(false)
  const [backendBase, setBackendBase] = useState(null)
  const chatRef = useRef(null)

  useEffect(() => {
    try {
      const stored = localStorage.getItem("cvchat_dark")
      const isDark = stored === "1"
      setDark(isDark)
    if (isDark) document.documentElement.classList.add("dark")
    else document.documentElement.classList.remove("dark")
    } catch (e) {
      // ignore
    }
  }, [])

  function toggleDark() {
    const next = !dark
    setDark(next)
    try {
      localStorage.setItem("cvchat_dark", next ? "1" : "0")
    } catch (e) {}
    if (next) document.documentElement.classList.add("dark")
    else document.documentElement.classList.remove("dark")
  }

  // Keep the newest message pinned at the top of the chat area (right below the input).
  // When messages change, scroll to top so the most recent message is visible under the input.
  useEffect(() => {
    const el = chatRef.current
    if (el) {
      setTimeout(() => {
        el.scrollTop = 0
      }, 50)
    }
  }, [messages.length])

  return (
    <div className="container">
      <button className="theme-toggle" onClick={toggleDark} title="Toggle dark mode">{dark ? '☀️' : '🌙'}</button>
  <Upload onNewMessage={(m) => setMessages((s) => [m, ...s])} onBackendFound={(b) => setBackendBase(b)} />
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold">CV Chat PoC</h1>
        <div className="text-sm text-slate-600">Backend: <span className="font-mono">{backendBase || 'unknown'}</span></div>
      </div>
      <div ref={chatRef} className="chat">
        {messages.map((m, i) => {
          // m is an object: { type: 'user'|'assistant'|'info'|'error', text }
          if (!m || typeof m !== "object") {
            return (
              <div key={i} className="message">
                {String(m)}
              </div>
            )
          }

          if (m.type === "user") {
            return (
              <div key={i} className="message user-message">
                <div className="user-prompt">{m.text}</div>
              </div>
            )
          }

          if (m.type === "assistant") {
            return (
              <div key={i}>
                <div className="message assistant-message">
                  <div className="assistant-reply">{m.text}</div>
                </div>
                <div className="sep" />
              </div>
            )
          }

          // info / error
          return (
            <div key={i} className={`message ${m.type || "info"}`}>
              {m.text}
            </div>
          )
        })}
      </div>
    </div>
  )
}
