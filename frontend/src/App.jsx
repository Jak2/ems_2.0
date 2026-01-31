import React, { useState, useRef, useEffect } from "react"
import Upload from "./Upload"

// Main application component. Holds the global message list and renders
// the Upload and NL-CRUD components. Messages are displayed in the chat pane.

export default function App() {
  const [messages, setMessages] = useState([])
  const chatRef = useRef(null)

  // Smooth-scroll the chat container to show newest messages with a small
  // offset so the latest QA pair doesn't hug the absolute bottom. We keep
  // this light-weight and defensive (clamp values) so it works across
  // different layouts.
  function scrollToBottom(offset = 40) {
    const el = chatRef.current
    if (!el) return
    // compute desired scrollTop: max scroll minus offset
    const max = el.scrollHeight - el.clientHeight
    const target = Math.max(0, Math.floor(max - offset))
    try {
      el.scrollTo({ top: target, behavior: "smooth" })
    } catch (err) {
      // fallback for older environments
      el.scrollTop = target
    }
  }

  // When messages change, scroll after a short delay so the layout has
  // settled (images/avatars or font loads). The delay is small and
  // improves perceived smoothness.
  useEffect(() => {
    if (!chatRef.current) return
    const t = setTimeout(() => scrollToBottom(48), 60)
    return () => clearTimeout(t)
  }, [messages])

  return (
    <div className="container">
  <h1>CV Chat PoC</h1>
  <Upload onNewMessage={(m) => setMessages((s) => [m, ...s])} />
      <div className="chat" ref={chatRef}>
        {messages.slice().reverse().map((m, i) => {
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
