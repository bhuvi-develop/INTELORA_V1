/**
 * Live stream client.
 *
 * One multiplexed WebSocket carries every live channel — KPIs, asset
 * summaries, telemetry, alerts and intelligence — rather than a socket per
 * feature. Subscribers register by message type and the client routes to them.
 *
 * The critical design decision here is **coalescing**. The Digital Twin emits
 * at 1 Hz and the server pushes an aggregated tick on every one of them. Naive
 * handling would call `setState` on each message, re-rendering the entire
 * Cockpit — nine KPI cards, three asset cards, seven charts — once per message
 * regardless of whether the browser was ready to paint. Instead messages are
 * buffered and flushed on an animation frame, so React does at most one pass
 * per painted frame and the work collapses automatically when the tab is
 * backgrounded.
 *
 * Reconnection uses exponential backoff with jitter, so a backend restart does
 * not produce a synchronised stampede from every open dashboard.
 */

import { LIVE, config } from '@/constants/config'

export type LiveMessageType =
  | 'hello'
  | 'tick'
  | 'telemetry'
  | 'alert'
  | 'intelligence'
  | 'engine_status'
  | 'pong'

export interface LiveMessage<T = unknown> {
  type: LiveMessageType
  timestamp: string
  payload: T
}

export type ConnectionState = 'connecting' | 'open' | 'closed' | 'reconnecting'

type Listener<T = unknown> = (payload: T, message: LiveMessage<T>) => void
type StateListener = (state: ConnectionState) => void

class LiveStreamClient {
  private socket: WebSocket | null = null
  private state: ConnectionState = 'closed'
  private attempts = 0
  private reconnectTimer: number | null = null
  private heartbeatTimer: number | null = null
  private frame: number | null = null
  private disposed = false

  private readonly listeners = new Map<LiveMessageType, Set<Listener>>()
  private readonly stateListeners = new Set<StateListener>()

  /** Latest message per type, flushed together on the next animation frame. */
  private readonly pending = new Map<LiveMessageType, LiveMessage>()

  /** Reference count: the socket opens on the first subscriber, closes after the last. */
  private consumers = 0

  // --- Subscription --------------------------------------------------------

  on<T>(type: LiveMessageType, listener: Listener<T>): () => void {
    const set = this.listeners.get(type) ?? new Set<Listener>()
    set.add(listener as Listener)
    this.listeners.set(type, set)
    return () => {
      set.delete(listener as Listener)
    }
  }

  onStateChange(listener: StateListener): () => void {
    this.stateListeners.add(listener)
    listener(this.state)
    return () => {
      this.stateListeners.delete(listener)
    }
  }

  /** Acquire the connection. Returns a release function. */
  acquire(): () => void {
    this.consumers += 1
    if (this.consumers === 1) this.connect()
    return () => {
      this.consumers = Math.max(0, this.consumers - 1)
      if (this.consumers === 0) this.disconnect()
    }
  }

  get connectionState(): ConnectionState {
    return this.state
  }

  // --- Connection ----------------------------------------------------------

  private setState(next: ConnectionState): void {
    if (this.state === next) return
    this.state = next
    this.stateListeners.forEach((listener) => listener(next))
  }

  private connect(): void {
    if (this.disposed) return
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return
    }

    this.setState(this.attempts === 0 ? 'connecting' : 'reconnecting')

    let socket: WebSocket
    try {
      socket = new WebSocket(config.wsUrl)
    } catch {
      this.scheduleReconnect()
      return
    }

    this.socket = socket

    socket.onopen = () => {
      this.attempts = 0
      this.setState('open')
      this.startHeartbeat()
    }

    socket.onmessage = (event) => {
      try {
        this.enqueue(JSON.parse(event.data as string) as LiveMessage)
      } catch {
        // A malformed frame is dropped rather than tearing down the stream.
      }
    }

    socket.onerror = () => {
      // `onclose` always follows; reconnection is handled there so it does not
      // run twice.
    }

    socket.onclose = () => {
      this.stopHeartbeat()
      this.socket = null
      if (this.consumers > 0 && !this.disposed) {
        this.scheduleReconnect()
      } else {
        this.setState('closed')
      }
    }
  }

  private disconnect(): void {
    this.clearReconnect()
    this.stopHeartbeat()
    if (this.frame !== null) {
      cancelAnimationFrame(this.frame)
      this.frame = null
    }
    this.pending.clear()

    const socket = this.socket
    this.socket = null
    if (socket) {
      socket.onclose = null
      socket.close()
    }
    this.setState('closed')
  }

  private scheduleReconnect(): void {
    this.clearReconnect()
    this.attempts += 1

    // Exponential backoff with jitter: without the random component every
    // dashboard reconnects in lockstep and hammers a recovering backend.
    const base = Math.min(
      LIVE.reconnectBaseMs * 2 ** (this.attempts - 1),
      LIVE.reconnectMaxMs,
    )
    const delay = base * (0.7 + Math.random() * 0.6)

    this.setState('reconnecting')
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay)
  }

  private clearReconnect(): void {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = window.setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send('ping')
      }
    }, LIVE.heartbeatMs)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  // --- Coalescing ----------------------------------------------------------

  /**
   * Buffer a message and schedule a flush.
   *
   * Only the newest message of each type is retained: at 1 Hz a superseded
   * KPI tick has no value, and delivering both would double the render work to
   * show the same final state. Telemetry is the exception — it is a stream of
   * distinct events — so those payloads are concatenated instead of replaced.
   */
  private enqueue(message: LiveMessage): void {
    if (message.type === 'pong') return

    if (message.type === 'telemetry') {
      const existing = this.pending.get('telemetry')
      if (existing && Array.isArray(existing.payload) && Array.isArray(message.payload)) {
        this.pending.set('telemetry', {
          ...message,
          payload: [...(existing.payload as unknown[]), ...(message.payload as unknown[])],
        })
      } else {
        this.pending.set('telemetry', message)
      }
    } else {
      this.pending.set(message.type, message)
    }

    if (this.frame === null) {
      this.frame = requestAnimationFrame(() => this.flush())
    }
  }

  private flush(): void {
    this.frame = null
    const batch = Array.from(this.pending.values())
    this.pending.clear()

    for (const message of batch) {
      const listeners = this.listeners.get(message.type)
      if (!listeners?.size) continue
      for (const listener of listeners) {
        try {
          listener(message.payload, message)
        } catch {
          // One faulty subscriber must not stop the others from updating.
        }
      }
    }
  }

  /** Tear down permanently. Used only by hot-module replacement. */
  dispose(): void {
    this.disposed = true
    this.disconnect()
    this.listeners.clear()
    this.stateListeners.clear()
  }
}

export const liveStream = new LiveStreamClient()

if (import.meta.hot) {
  import.meta.hot.dispose(() => liveStream.dispose())
}
