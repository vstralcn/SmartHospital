from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy import select
from websockets.protocol import State as WsState


def _ws_is_open(ws) -> bool:
    """Check if a websockets connection is still open (compatible with v12+)."""
    if hasattr(ws, "state"):
        return ws.state == WsState.OPEN
    # Fallback for older versions
    if hasattr(ws, "closed"):
        return not ws.closed
    return True


from database import SessionLocal
from models import AsrConfig
from services.tencent_asr_service import TencentAsrService

router = APIRouter()

tencent_asr_service = TencentAsrService()


def _get_active_asr_config() -> AsrConfig | None:
    with SessionLocal() as db:
        stmt = (
            select(AsrConfig)
            .where(
                AsrConfig.is_active.is_(True),
                AsrConfig.is_enabled.is_(True),
            )
            .limit(1)
        )
        config = db.scalar(stmt)
        if config:
            db.expunge(config)
        return config


@router.websocket("/ws/audio")
async def audio_websocket(websocket: WebSocket):
    await websocket.accept()
    session_id: str | None = None
    sessions: dict[str, dict[str, object]] = websocket.app.state.sessions
    tencent_ws = None

    try:
        init_data = await websocket.receive_text()
        config = json.loads(init_data)
        session_id = str(config.get("session_id") or "")

        if session_id not in sessions:
            sessions[session_id] = {
                "dialogues": [],
                "structured": None,
                "emr_text": "",
                "risk_alerts": [],
                "status": "recording",
            }

        asr_config = _get_active_asr_config()

        if asr_config is None:
            logger.warning("No active ASR config found, using ack mode")
            await websocket.send_json(
                {"type": "ready", "session_id": session_id, "asr_mode": "ack"}
            )
            while True:
                data = await websocket.receive_bytes()
                await websocket.send_json(
                    {
                        "type": "ack",
                        "bytes_received": len(data),
                        "session_id": session_id,
                    }
                )
        else:
            wss_url = tencent_asr_service.generate_sign_url(
                appid=asr_config.appid,
                secret_id=asr_config.secret_id,
                secret_key=asr_config.secret_key,
                engine_model_type=asr_config.engine_model_type,
            )

            import websockets

            tencent_ws = await asyncio.wait_for(
                websockets.connect(wss_url),
                timeout=10,
            )

            init_resp = await asyncio.wait_for(tencent_ws.recv(), timeout=10)
            init_result = json.loads(init_resp)
            if init_result.get("code") != 0:
                logger.error(f"Tencent ASR handshake failed: {init_result}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"语音识别服务连接失败：{init_result.get('message', '')}",
                        "session_id": session_id,
                    }
                )
                return

            logger.info(f"Tencent ASR connected for session {session_id}")
            await websocket.send_json(
                {"type": "ready", "session_id": session_id, "asr_mode": "tencent"}
            )

            stop_event = asyncio.Event()
            relay_stats = {
                "chunk_count": 0,
                "byte_count": 0,
                "last_audio_at": asyncio.get_running_loop().time(),
            }

            async def forward_results():
                """Receive results from Tencent ASR and forward to frontend."""
                try:
                    async for message in tencent_ws:
                        if stop_event.is_set():
                            break
                        if isinstance(message, bytes):
                            message = message.decode("utf-8", errors="ignore")
                        try:
                            result = json.loads(message)
                        except json.JSONDecodeError:
                            continue

                        code = result.get("code", -1)
                        if code != 0:
                            logger.warning(f"Tencent ASR error: {result}")
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": result.get(
                                        "message", "语音识别服务错误"
                                    ),
                                    "session_id": session_id,
                                    "code": code,
                                }
                            )
                            stop_event.set()
                            break

                        if result.get("final") == 1:
                            logger.info(
                                f"Tencent ASR final event received for session {session_id}"
                            )
                            stop_event.set()
                            break

                        voice_result = result.get("result", {})
                        slice_type = voice_result.get("slice_type", -1)
                        text = voice_result.get("voice_text_str", "").strip()

                        if not text:
                            continue

                        payload = {
                            "text": text,
                            "session_id": session_id,
                            "slice_type": slice_type,
                            "index": voice_result.get("index"),
                            "start_time": voice_result.get("start_time"),
                            "end_time": voice_result.get("end_time"),
                        }

                        if slice_type == 2:
                            await websocket.send_json(
                                {
                                    "type": "final_result",
                                    **payload,
                                }
                            )
                        else:
                            await websocket.send_json(
                                {
                                    "type": "partial_result",
                                    **payload,
                                }
                            )
                except Exception as e:
                    if not stop_event.is_set():
                        logger.error(f"Error receiving from Tencent ASR: {e}")

            async def forward_audio():
                """Receive audio from frontend and forward to Tencent ASR."""
                try:
                    while not stop_event.is_set():
                        try:
                            msg = await asyncio.wait_for(
                                websocket.receive(), timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            now = asyncio.get_running_loop().time()
                            if (
                                relay_stats["chunk_count"]
                                and now - relay_stats["last_audio_at"] >= 5
                            ):
                                logger.info(
                                    f"ASR relay heartbeat session={session_id} chunks={relay_stats['chunk_count']} bytes={relay_stats['byte_count']} idle={now - relay_stats['last_audio_at']:.1f}s"
                                )
                            continue

                        if msg.get("bytes"):
                            if tencent_ws:
                                try:
                                    if _ws_is_open(tencent_ws):
                                        relay_stats["chunk_count"] += 1
                                        relay_stats["byte_count"] += len(msg["bytes"])
                                        relay_stats["last_audio_at"] = (
                                            asyncio.get_running_loop().time()
                                        )
                                        await tencent_ws.send(msg["bytes"])
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to send audio to Tencent ASR: {e}"
                                    )
                        elif msg.get("text"):
                            # JSON control message (e.g. {"type": "end"})
                            try:
                                ctrl = json.loads(msg["text"])
                                if ctrl.get("type") == "end":
                                    logger.info(
                                        f"Received end signal for session {session_id}"
                                    )
                                    if tencent_ws:
                                        try:
                                            if _ws_is_open(tencent_ws):
                                                await tencent_ws.send(
                                                    json.dumps({"type": "end"})
                                                )
                                        except Exception as e:
                                            logger.warning(
                                                f"Failed to send end signal to Tencent ASR: {e}"
                                            )
                                    # Let forward_results drain remaining messages
                                    return
                            except json.JSONDecodeError:
                                pass
                except WebSocketDisconnect:
                    if tencent_ws:
                        try:
                            if _ws_is_open(tencent_ws):
                                await tencent_ws.send(json.dumps({"type": "end"}))
                        except Exception:
                            pass
                    stop_event.set()
                except Exception as e:
                    if not stop_event.is_set():
                        logger.error(f"Error forwarding audio: {e}")
                    stop_event.set()

            results_task = asyncio.create_task(forward_results())
            audio_task = asyncio.create_task(forward_audio())

            await audio_task
            try:
                await asyncio.wait_for(results_task, timeout=8.0)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timed out waiting for Tencent ASR final results for session {session_id}"
                )
                stop_event.set()
                results_task.cancel()
                try:
                    await results_task
                except (asyncio.CancelledError, Exception):
                    pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
    finally:
        if tencent_ws:
            try:
                if _ws_is_open(tencent_ws):
                    await tencent_ws.close()
            except Exception:
                pass
