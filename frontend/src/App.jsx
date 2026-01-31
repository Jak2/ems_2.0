import React, { useState } from "react"
import Upload from "./Upload"

// Main application component. Holds the global message list and renders
// the Upload and NL-CRUD components. Messages are displayed in the chat pane.

export default function App() {
  const [messages, setMessages] = useState([])

  return (
    <div className="container">
  <h1>CV Chat PoC</h1>
  <Upload onNewMessage={(m) => setMessages((s) => [m, ...s])} />
      <div className="chat">
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
