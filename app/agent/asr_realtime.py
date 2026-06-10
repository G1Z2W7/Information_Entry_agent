from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed


@dataclass
class AsrRealtimeConfig:
    api_key: str
    base_url: str
    model: str

    @property
    def upstream_url(self) -> str:
        separator = "&" if "?" in self.base_url else "?"
        return f"{self.base_url}{separator}model={self.model}"


def load_asr_realtime_config_from_env() -> AsrRealtimeConfig:
    api_key = os.getenv("ASR_API_KEY", "").strip()
    base_url = normalize_asr_base_url(os.getenv("ASR_BASE_URL", "").strip())
    model = os.getenv("ASR_MODEL", "").strip()

    if not api_key:
        raise RuntimeError("ASR_API_KEY is not configured.")
    if not base_url:
        raise RuntimeError("ASR_BASE_URL is not configured.")
    if not model:
        raise RuntimeError("ASR_MODEL is not configured.")

    return AsrRealtimeConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


def normalize_asr_base_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    normalized = raw_url.strip()
    if normalized.startswith("hwss://"):
        normalized = "wss://" + normalized.removeprefix("hwss://")
    if normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


async def bridge_qwen_realtime_asr(client_ws: WebSocket) -> None:
    config = load_asr_realtime_config_from_env()
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    async with ws_connect(config.upstream_url, additional_headers=headers, proxy=None) as upstream:
        await _forward_client_session(client_ws, upstream)


async def _forward_client_session(client_ws: WebSocket, upstream: Any) -> None:
    session_started = False
    stop_requested = False

    try:
        while True:
            message = await client_ws.receive()
            if message.get("type") == "websocket.disconnect":
                if not stop_requested:
                    await _safe_finish_session(upstream)
                break

            text_data = message.get("text")
            bytes_data = message.get("bytes")

            if text_data is not None:
                payload = json.loads(text_data)
                event_type = payload.get("type")
                if event_type == "start":
                    await _send_session_update(upstream)
                    session_started = True
                    await client_ws.send_json({"type": "starting"})
                    await _pump_upstream_until_ready(client_ws, upstream)
                    continue

                if event_type == "stop":
                    stop_requested = True
                    if session_started:
                        await _safe_finish_session(upstream)
                        await _pump_upstream_until_finished(client_ws, upstream)
                    break

            if bytes_data is not None:
                if not session_started:
                    continue
                await upstream.send(
                    json.dumps(
                        {
                            "event_id": f"event_audio_{os.urandom(4).hex()}",
                            "type": "input_audio_buffer.append",
                            "audio": _encode_audio(bytes_data),
                        }
                    )
                )
                await _drain_upstream_messages(client_ws, upstream)
    finally:
        try:
            await client_ws.close()
        except RuntimeError:
            pass


async def _send_session_update(upstream: Any) -> None:
    await upstream.send(
        json.dumps(
            {
                "event_id": "event_session_start",
                "type": "session.update",
                "session": {
                    "modalities": ["text"],
                    "input_audio_format": "pcm",
                    "sample_rate": 16000,
                    "turn_detection": None,
                },
            }
        )
    )


async def _pump_upstream_until_ready(client_ws: WebSocket, upstream: Any) -> None:
    while True:
        raw_message = await upstream.recv()
        should_continue = await _relay_upstream_message(client_ws, raw_message)
        if not should_continue:
            break


async def _pump_upstream_until_finished(client_ws: WebSocket, upstream: Any) -> None:
    while True:
        try:
            raw_message = await upstream.recv()
        except ConnectionClosed:
            break
        should_continue = await _relay_upstream_message(client_ws, raw_message)
        if not should_continue:
            break


async def _drain_upstream_messages(client_ws: WebSocket, upstream: Any) -> None:
    while True:
        try:
            raw_message = await asyncio.wait_for(upstream.recv(), timeout=0.01)
        except asyncio.TimeoutError:
            break
        except ConnectionClosed:
            break
        should_continue = await _relay_upstream_message(client_ws, raw_message)
        if not should_continue:
            break


async def _safe_finish_session(upstream: Any) -> None:
    try:
        await upstream.send(
            json.dumps(
                {
                    "event_id": "event_commit",
                    "type": "input_audio_buffer.commit",
                }
            )
        )
        await upstream.send(
            json.dumps(
                {
                    "event_id": "event_finish",
                    "type": "session.finish",
                }
            )
        )
    except ConnectionClosed:
        return


async def _relay_upstream_message(client_ws: WebSocket, raw_message: str) -> bool:
    payload = json.loads(raw_message)
    event_type = payload.get("type", "")

    if event_type == "session.created":
        return True

    if event_type == "session.updated":
        await client_ws.send_json({"type": "ready"})
        return False

    if event_type == "conversation.item.input_audio_transcription.text":
        await client_ws.send_json(
            {
                "type": "partial",
                "text": payload.get("text", ""),
                "stash": payload.get("stash", ""),
                "emotion": payload.get("emotion"),
            }
        )
        return True

    if event_type == "conversation.item.input_audio_transcription.completed":
        await client_ws.send_json(
            {
                "type": "final",
                "text": payload.get("transcript", ""),
                "emotion": payload.get("emotion"),
            }
        )
        return True

    if event_type == "conversation.item.input_audio_transcription.failed":
        error = payload.get("error", {})
        await client_ws.send_json(
            {
                "type": "error",
                "message": error.get("message", "ASR transcription failed."),
            }
        )
        return False

    if event_type == "session.finished":
        await client_ws.send_json({"type": "finished"})
        return False

    if event_type == "error":
        error = payload.get("error", {})
        await client_ws.send_json(
            {
                "type": "error",
                "message": error.get("message", "ASR upstream error."),
            }
        )
        return False

    return True


def _encode_audio(audio_bytes: bytes) -> str:
    import base64

    return base64.b64encode(audio_bytes).decode("utf-8")
