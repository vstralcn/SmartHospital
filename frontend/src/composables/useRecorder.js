import { ref, onUnmounted } from 'vue'
import { useWebSocket } from './useWebSocket'

const TARGET_SAMPLE_RATE = 16000
const CHANNEL_COUNT = 1
const PCM_CHUNK_MS = 200
const BYTES_PER_SAMPLE = 2
const CHUNK_SIZE = (TARGET_SAMPLE_RATE * PCM_CHUNK_MS * BYTES_PER_SAMPLE) / 1000

export function useRecorder() {
  const isRecording = ref(false)
  const partialText = ref('')
  const finalTexts = ref([])
  const recordingStartTime = ref(0)
  const asrMode = ref('')
  const asrError = ref('')
  const mediaRecorder = ref(null)
  const stream = ref(null)
  const audioContext = ref(null)
  const processor = ref(null)

  let asrReadyResolve = null
  let flushTimer = null
  let pcmBuffer = new Int16Array(0)
  let statsTimer = null
  let sentChunkCount = 0
  let sentByteCount = 0

  const { isConnected, connect, send, disconnect } = useWebSocket()

  function resetPcmBuffer() {
    pcmBuffer = new Int16Array(0)
  }

  function resetStats() {
    sentChunkCount = 0
    sentByteCount = 0
  }

  function startStatsTimer() {
    stopStatsTimer()
    statsTimer = setInterval(() => {
      if (!isRecording.value) return
      const state = audioContext.value?.state || 'unknown'
      console.info('[Recorder] state=%s chunks=%d bytes=%d buffered=%d', state, sentChunkCount, sentByteCount, pcmBuffer.byteLength)
    }, 5000)
  }

  function stopStatsTimer() {
    if (statsTimer) {
      clearInterval(statsTimer)
      statsTimer = null
    }
  }

  function appendPcmChunk(chunk) {
    const next = new Int16Array(pcmBuffer.length + chunk.length)
    next.set(pcmBuffer)
    next.set(chunk, pcmBuffer.length)
    pcmBuffer = next
  }

  function flushPcmChunk(force = false) {
    if (!pcmBuffer.length) return
    if (!force && pcmBuffer.byteLength < CHUNK_SIZE) return

    const samplesToSend = force ? pcmBuffer.length : CHUNK_SIZE / BYTES_PER_SAMPLE
    const payload = pcmBuffer.slice(0, samplesToSend)
    pcmBuffer = pcmBuffer.slice(samplesToSend)
    sentChunkCount += 1
    sentByteCount += payload.byteLength
    send(payload.buffer)
  }

  function startFlushTimer() {
    stopFlushTimer()
    flushTimer = setInterval(() => {
      if (!isRecording.value) return
      flushPcmChunk()
    }, PCM_CHUNK_MS)
  }

  function stopFlushTimer() {
    if (flushTimer) {
      clearInterval(flushTimer)
      flushTimer = null
    }
  }

  function convertFloat32ToInt16(float32) {
    const int16 = new Int16Array(float32.length)
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]))
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return int16
  }

  function onWsMessage(data) {
    if (data.type === 'ready') {
      asrMode.value = data.asr_mode || 'unknown'
      if (asrReadyResolve) {
        asrReadyResolve(data.asr_mode)
        asrReadyResolve = null
      }
    } else if (data.type === 'error') {
      asrError.value = data.message || '语音识别服务错误'
      console.error('ASR error:', data.message)
    } else if (data.type === 'partial_result') {
      partialText.value = data.text
    } else if (data.type === 'final_result') {
      if (data.text) {
        finalTexts.value.push({
          text: data.text,
          start: typeof data.start_time === 'number' ? data.start_time / 1000 : null,
          end: typeof data.end_time === 'number' ? data.end_time / 1000 : null,
          index: data.index ?? null,
        })
      }
      partialText.value = ''
    }
  }

  async function startRecording(sessionId) {
    asrMode.value = ''
    asrError.value = ''
    finalTexts.value = []
    partialText.value = ''
    resetPcmBuffer()
    resetStats()

    try {
      connect('/ws/audio', onWsMessage)

      await new Promise((resolve, reject) => {
        const check = setInterval(() => {
          if (isConnected.value) {
            clearInterval(check)
            resolve()
          }
        }, 100)
        setTimeout(() => {
          clearInterval(check)
          reject(new Error('WebSocket connection timeout'))
        }, 5000)
      })

      const readyPromise = new Promise((resolve, reject) => {
        asrReadyResolve = resolve
        setTimeout(() => {
          asrReadyResolve = null
          reject(new Error('ASR ready timeout'))
        }, 15000)
      })

      send({ session_id: sessionId, sample_rate: TARGET_SAMPLE_RATE })

      const mode = await readyPromise
      if (mode === 'ack') {
        throw new Error('NO_ASR_CONFIG')
      }

      stream.value = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: TARGET_SAMPLE_RATE,
          channelCount: CHANNEL_COUNT,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      audioContext.value = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: TARGET_SAMPLE_RATE,
      })
      const context = audioContext.value
      context.onstatechange = () => {
        console.info('[Recorder] AudioContext state=%s', context.state)
      }
      if (context.state !== 'running') {
        await context.resume()
      }
      const source = context.createMediaStreamSource(stream.value)
      processor.value = context.createScriptProcessor(4096, CHANNEL_COUNT, CHANNEL_COUNT)

      processor.value.onaudioprocess = (e) => {
        if (!isRecording.value) return
        const float32 = e.inputBuffer.getChannelData(0)
        appendPcmChunk(convertFloat32ToInt16(float32))
      }

      source.connect(processor.value)
      processor.value.connect(audioContext.value.destination)

      recordingStartTime.value = Date.now()
      isRecording.value = true
      startFlushTimer()
      startStatsTimer()
    } catch (err) {
      console.error('Failed to start recording:', err)
      stopRecording('start-failed')
      throw err
    }
  }

  function stopRecording(reason = 'unknown') {
    console.warn('[Recorder] stopRecording reason=%s state=%s stack=%s', reason, audioContext.value?.state || 'none', new Error().stack)
    isRecording.value = false
    stopFlushTimer()
    stopStatsTimer()
    flushPcmChunk(true)

    if (processor.value) {
      processor.value.disconnect()
      processor.value = null
    }
    if (audioContext.value) {
      audioContext.value.close()
      audioContext.value = null
    }
    if (stream.value) {
      stream.value.getTracks().forEach((t) => t.stop())
      stream.value = null
    }

    // Send end signal before disconnecting (Tencent ASR requires this)
    try {
      send({ type: 'end' })
    } catch {
      // ignore if already disconnected
    }

    resetPcmBuffer()

    // Disconnect WebSocket to prevent stale connections from interfering
    // with future sessions
    setTimeout(() => {
      disconnect()
    }, 500)

    partialText.value = ''
  }

  onUnmounted(() => {
    stopRecording('unmounted')
  })

  return {
    isRecording,
    isConnected,
    partialText,
    finalTexts,
    recordingStartTime,
    asrMode,
    asrError,
    startRecording,
    stopRecording,
  }
}
