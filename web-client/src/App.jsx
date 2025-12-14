import React, { useState, useEffect, useRef } from 'react'
import { chat } from './api'

// Import avatars
import botIcon from './images/bot.png'
import userIcon from './images/user.png'

export default function App() {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(false)
  const chatRef = useRef(null)

  useEffect(() => {
    (async () => {
      try {
        setLoading(true)
        const res = await chat(null, 'hi')
        setSessionId(res.session_id)
        addBotMessage(res.reply)
      } catch (err) {
        addBotMessage('Sorry the chatbot is currently unavailable.')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  function addUserMessage(txt) {
    setMessages(m => [...m, { role: 'user', text: txt }])
  }

  function addBotMessage(txt, product = null) {
    setMessages(m => [...m, { role: 'bot', text: txt, product }])
  }

  async function handleSend(msgText = null) {
    const msg = msgText || input.trim()
    if (!msg) return

    addUserMessage(msg)
    setInput('')
    setLoading(true)

    try {
      const res = await chat(sessionId, msg)
      setSessionId(res.session_id)
      addBotMessage(res.reply, res.product)
      setSuggestions(res.suggestions || [])
    } catch {
      addBotMessage('Sorry I could not reach the server. Please try again later.')
    } finally {
      setLoading(false)
      setTimeout(() => {
        if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
      }, 50)
    }
  }

  return (
    <div className="app">
      <div className="header">
        <h2>Lato Chatbot</h2>
      </div>

      <div className="chatbox" ref={chatRef}>
        {messages.map((m, i) => (
          <div
            key={i}
            className={`messageRow ${m.role === 'user' ? 'userRow' : 'botRow'}`}
          >
            <img
              className="avatar"
              src={m.role === 'user' ? userIcon : botIcon}
              alt="avatar"
            />

            <div className={`bubble ${m.role}`}>
              {m.text.split('\n').map((line, idx) => (
                <div key={idx}>{line}</div>
              ))}

              {m.product && (
                <div
                  className="productCard"
                  onClick={() => handleSend(m.product.name)}
                >
                  {m.product.image && (
                    <img src={m.product.image} alt={m.product.name} />
                  )}

                  <div>
                    <strong>{m.product.name}</strong>
                    <div>SKU: {m.product.sku}</div>
                    {m.product.description && <div>{m.product.description}</div>}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="messageRow botRow">
            <img className="avatar" src={botIcon} alt="bot" />
            <div className="bubble bot typing">Typing...</div>
          </div>
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="suggestionBox">
          <strong>Suggestions:</strong>
          <div className="suggestionButtons">
            {suggestions.map((s, idx) => (
              <button key={idx} onClick={() => handleSend(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="inputRow">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Ask me about Lato products..."
        />
        <button onClick={() => handleSend()}>Send</button>
      </div>
    </div>
  )
}
