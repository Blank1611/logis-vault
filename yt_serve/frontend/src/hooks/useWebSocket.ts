import { useEffect, useRef } from 'react'

export function useWebSocketEvents(onEvent: (type: string, data: any) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const onEventRef = useRef(onEvent)

  // Keep the callback ref up to date
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    // Connect to WebSocket using current host and port (or proxy)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/events`
    
    console.log('[WebSocket] Attempting to connect to:', wsUrl)
    
    let ws: WebSocket
    try {
      ws = new WebSocket(wsUrl)
    } catch (error) {
      console.error('[WebSocket] Failed to create WebSocket:', error)
      return
    }
    
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[WebSocket] ✓ Connected to events endpoint')
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type !== 'pong') {
          console.log('[WebSocket] Received event:', message)
          onEventRef.current(message.type, message.data)
        }
      } catch (error) {
        console.error('[WebSocket] Error parsing message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Connection error:', error)
      console.error('[WebSocket] Make sure backend is running on port 8000')
    }

    ws.onclose = (event) => {
      console.log('[WebSocket] Disconnected. Code:', event.code, 'Reason:', event.reason)
    }

    // Keep connection alive with ping
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000) // Ping every 30 seconds

    // Cleanup
    return () => {
      clearInterval(pingInterval)
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, []) // Empty deps - only connect once on mount

  return wsRef
}
