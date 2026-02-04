import React, { useState, useRef, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import Upload from "./Upload"

// Main application component. Holds the global message list and renders
// the Upload and NL-CRUD components. Messages are displayed in the chat pane.

export default function App() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const chatRef = useRef(null)

  // Smooth-scroll the chat container to the absolute bottom to show the
  // latest message. Uses smooth behavior for better UX.
  function scrollToBottom() {
    const el = chatRef.current
    if (!el) return
    try {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
    } catch (err) {
      // fallback for older environments
      el.scrollTop = el.scrollHeight
    }
  }

  // When messages change, scroll after a short delay so the layout has
  // settled (DOM updates, content rendering). This ensures the latest
  // response is always visible at the bottom.
  useEffect(() => {
    if (!chatRef.current) return
    const t = setTimeout(() => scrollToBottom(), 100)
    return () => clearTimeout(t)
  }, [messages])

  return (
    <div className="container">
      <h1 className="app-title">ChatBot</h1>
      {/* Loading progress bar - 2px thin bar at top of chat */}
      {isLoading && (
        <div className="loading-bar-container">
          <div className="loading-bar"></div>
        </div>
      )}
      <div className="chat" ref={chatRef}>
        {messages.slice().reverse().map((m, i) => {
          // m is an object: { type: 'user'|'assistant'|'info'|'error', text, filename? }
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
                  <div className="assistant-reply markdown-content">
                    <ReactMarkdown>{m.text}</ReactMarkdown>
                  </div>
                  {m.responseTime && (
                    <div className="response-time">{m.responseTime}s</div>
                  )}
                </div>
                <div className="sep" />
              </div>
            )
          }

          if (m.type === "attachment") {
            return (
              <div key={i} className="message attachment-message">
                <span className="attachment-icon">📎</span>
                <span className="attachment-name">{m.filename}</span>
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
      <Upload
        onNewMessage={(m) => setMessages((s) => [m, ...s])}
        onLoadingChange={setIsLoading}
      />
    </div>
  )
}

