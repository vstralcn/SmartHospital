import { ref, onUnmounted } from 'vue'

export function useWebSocket() {
  const ws = ref(null)
  const isConnected = ref(false)
  const lastMessage = ref(null)

  let onCloseCallback = null

  function connect(url, onMessage, onClose) {
    // Close any existing connection first to prevent race conditions
    if (ws.value) {
      const oldWs = ws.value
      ws.value = null
      onCloseCallback = null
      try {
        oldWs.onclose = null
        oldWs.onerror = null
        oldWs.onmessage = null
        oldWs.close()
      } catch {
        // ignore
      }
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}${url}`

    const socket = new WebSocket(wsUrl)
    ws.value = socket
    onCloseCallback = onClose

    socket.onopen = () => {
      // Only update state if this is still the current connection
      if (ws.value === socket) {
        isConnected.value = true
      }
    }

    socket.onmessage = (event) => {
      if (ws.value !== socket) return
      const data = JSON.parse(event.data)
      lastMessage.value = data
      if (onMessage) onMessage(data)
    }

    socket.onclose = () => {
      // Only handle close if this is still the current connection
      if (ws.value !== socket) return
      isConnected.value = false
      ws.value = null
      if (onCloseCallback) {
        const cb = onCloseCallback
        onCloseCallback = null
        cb()
      }
    }

    socket.onerror = (err) => {
      console.error('WebSocket error:', err)
      if (ws.value === socket) {
        isConnected.value = false
      }
    }
  }

  function send(data) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      if (typeof data === 'string' || data instanceof ArrayBuffer || data instanceof Blob) {
        ws.value.send(data)
      } else {
        ws.value.send(JSON.stringify(data))
      }
    }
  }

  function disconnect() {
    if (ws.value) {
      const socket = ws.value
      ws.value = null
      onCloseCallback = null
      socket.onclose = null
      socket.onerror = null
      socket.onmessage = null
      socket.close()
    }
    isConnected.value = false
  }

  onUnmounted(() => {
    disconnect()
  })

  return { ws, isConnected, lastMessage, connect, send, disconnect }
}
