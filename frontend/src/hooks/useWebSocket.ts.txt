import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const WS_BASE = `ws://${window.location.host}/ws`

interface WSMessage {
  type: 'status_change' | 'presence' | 'pong'
  incident_id?: string
  new_status?: string
  actor?: string
  notes?: string
  viewers?: string[]
}

export function useIncidentWebSocket(
  incidentId: string | null,
  userName = 'anonymous',
  onMessage?: (msg: WSMessage) => void
) {
  const wsRef = useRef<WebSocket | null>(null)
  const queryClient = useQueryClient()
  const pingInterval = useRef<ReturnType<typeof setInterval>>()

  const connect = useCallback(() => {
    if (!incidentId) return
    const url = `${WS_BASE}/incidents/${incidentId}?user_name=${encodeURIComponent(userName)}`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      console.log(`[WS] Connected to incident ${incidentId}`)
      // Keep-alive pings every 30s
      pingInterval.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30_000)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        if (msg.type === 'status_change') {
          // Invalidate React Query cache to trigger re-fetch
          queryClient.invalidateQueries({ queryKey: ['incident', incidentId] })
          queryClient.invalidateQueries({ queryKey: ['incidents'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard-counts'] })
        }
        onMessage?.(msg)
      } catch (e) {
        console.warn('[WS] Failed to parse message', e)
      }
    }

    ws.onclose = () => {
      console.log(`[WS] Disconnected from incident ${incidentId}. Reconnecting in 3s...`)
      clearInterval(pingInterval.current)
      setTimeout(connect, 3_000)
    }

    ws.onerror = (err) => {
      console.error('[WS] Error', err)
      ws.close()
    }

    wsRef.current = ws
  }, [incidentId, userName, queryClient, onMessage])

  useEffect(() => {
    connect()
    return () => {
      clearInterval(pingInterval.current)
      wsRef.current?.close()
    }
  }, [connect])

  return wsRef
}
