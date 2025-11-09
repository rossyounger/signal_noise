"""Helpers for executing transcription requests queued from Retool."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import psycopg
import requests

# Provider adapters return transcript text
ProviderFunc = Callable[[Path, str | None], str]


def fetch_request(conn: psycopg.Connection, request_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tr.id,
                   tr.document_id,
                   tr.provider,
                   tr.model,
                   tr.start_seconds,
                   tr.end_seconds,
                   d.title,
                   d.assets
            FROM transcription_requests tr
            JOIN documents d ON d.id = tr.document_id
            WHERE tr.id = %s
            """,
            (request_id,),
        )
        row = cur.fetchone()

    if not row:
        raise LookupError(f"Request {request_id} not found")

    keys = [
        "id",
        "document_id",
        "provider",
        "model",
        "start_seconds",
        "end_seconds",
        "title",
        "assets",
    ]
    return dict(zip(keys, row, strict=False))


def get_audio_asset(assets: list[dict[str, Any]] | None) -> dict[str, Any]:
    for asset in assets or []:
        if asset.get("type") == "audio":
            return asset
    raise ValueError("No audio asset available")


def download_audio(url: str, destination: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with destination.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)


def trim_audio(source: Path, dest: Path, start: float | None, end: float | None) -> None:
    """Trim or re-encode an audio clip to the requested window."""

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for segment transcription")

    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    if start is not None:
        cmd.extend(["-ss", str(start)])
    cmd.extend(["-i", str(source)])
    if start is not None and end is not None:
        duration = float(end) - float(start)
        if duration <= 0:
            raise ValueError("end_seconds must be greater than start_seconds")
        cmd.extend(["-t", str(duration)])
    elif end is not None:
        if end <= 0:
            raise ValueError("end_seconds must be greater than 0")
        cmd.extend(["-t", str(end)])
    cmd.extend(["-c:a", "libmp3lame", "-b:a", "128k", str(dest)])
    subprocess.run(cmd, check=True)


def openai_transcribe(audio_path: Path, model: str | None) -> str:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set for openai provider")

    client = OpenAI(api_key=api_key)
    model_name = model or "gpt-4o-mini-transcribe"
    with audio_path.open("rb") as audio_file:
        resp = client.audio.transcriptions.create(model=model_name, file=audio_file)
    return resp.text  # type: ignore[attr-defined]


def assemblyai_transcribe(audio_path: Path, model: str | None) -> str:
    import time

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY must be set for assemblyai provider")

    headers = {"authorization": api_key}

    with audio_path.open("rb") as audio_file:
        upload_resp = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            data=audio_file,
        )
    upload_resp.raise_for_status()
    upload_url = upload_resp.json()["upload_url"]

    payload = {"audio_url": upload_url}
    if model:
        payload["model"] = model
    create_resp = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers=headers,
        json=payload,
    )
    create_resp.raise_for_status()
    job = create_resp.json()
    transcript_id = job["id"]

    status = job["status"]
    while status not in {"completed", "error"}:
        time.sleep(5)
        status_resp = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers=headers,
        )
        status_resp.raise_for_status()
        job = status_resp.json()
        status = job["status"]

    if status == "error":
        raise RuntimeError(f"AssemblyAI error: {job.get('error')}")
    return job.get("text", "")


PROVIDERS: dict[str, ProviderFunc] = {
    "openai": openai_transcribe,
    "assemblyai": assemblyai_transcribe,
}


def create_segment_from_transcript(
    conn: psycopg.Connection,
    document_id: str,
    text: str,
    provider: str,
    request_id: str,
    start: float | None,
    end: float | None,
) -> None:
    from psycopg.types.json import Json

    provenance = {
        "source": "transcription",
        "request_id": str(request_id),
        "provider": provider,
    }
    start_offset = int(start) if start is not None else None
    end_offset = int(end) if end is not None else None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO segments (
                document_id,
                text,
                start_offset,
                end_offset,
                provenance,
                segment_status
            )
            VALUES (%s, %s, %s, %s, %s, 'raw text')
            """,
            (document_id, text, start_offset, end_offset, Json(provenance)),
        )


def process_transcription_request(
    conn: psycopg.Connection,
    request_id: str,
) -> str:
    """Download audio, run the provider, and create a proposed segment."""

    request = fetch_request(conn, request_id)
    provider_key = request["provider"]
    adapter = PROVIDERS.get(provider_key)
    if not adapter:
        raise ValueError(f"Unknown provider: {provider_key}")

    audio_asset = get_audio_asset(request.get("assets"))
    audio_url = audio_asset.get("url")
    if not audio_url:
        raise ValueError("Audio URL missing")

    start = request.get("start_seconds")
    end = request.get("end_seconds")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        audio_path = tmpdir_path / "source.mp3"
        download_audio(audio_url, audio_path)

        segment_path = audio_path
        if start is not None or end is not None:
            segment_path = tmpdir_path / "segment.mp3"
            trim_audio(audio_path, segment_path, start, end)

        transcript_text = adapter(segment_path, request.get("model"))

    provider_label = (
        provider_key
        if not request.get("model")
        else f"{provider_key}:{request['model']}"
    )
    create_segment_from_transcript(
        conn,
        document_id=request["document_id"],
        text=transcript_text,
        provider=provider_label,
        request_id=request_id,
        start=start,
        end=end,
    )

    return transcript_text


__all__ = [
    "process_transcription_request",
    "fetch_request",
]
