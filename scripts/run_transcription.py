"""Process a queued transcription request using selected provider."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
        raise SystemExit(f"Request {request_id} not found")
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


def get_audio_asset(assets: list[dict[str, Any]]) -> dict[str, Any]:
    for asset in assets or []:
        if asset.get("type") == "audio":
            return asset
    raise SystemExit("No audio asset available")


def download_audio(url: str, destination: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with destination.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)


def trim_audio(source: Path, dest: Path, start: float | None, end: float | None) -> None:
    """Trim or re-encode an audio clip to the requested window.

    We re-encode instead of stream-copying to avoid edge cases where
    timestamp discontinuities yield files OpenAI rejects as corrupted.
    """

    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required for segment transcription")

    cmd = [
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
        duration = max(end - start, 0)
        if duration <= 0:
            raise SystemExit("end_seconds must be greater than start_seconds")
        cmd.extend(["-t", str(duration)])
    elif end is not None:
        if end <= 0:
            raise SystemExit("end_seconds must be greater than 0")
        cmd.extend(["-t", str(end)])
    cmd.extend(["-c:a", "libmp3lame", "-b:a", "128k", str(dest)])
    subprocess.run(cmd, check=True)


def openai_transcribe(audio_path: Path, model: str | None) -> str:
    from openai import OpenAI

    client = OpenAI()
    model_name = model or "gpt-4o-mini-transcribe"
    with audio_path.open("rb") as audio_file:
        resp = client.audio.transcriptions.create(model=model_name, file=audio_file)
    return resp.text  # type: ignore[attr-defined]


def assembly_transcribe(audio_path: Path, model: str | None) -> str:
    import time

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise SystemExit("ASSEMBLYAI_API_KEY must be set")

    headers = {"authorization": api_key}

    # Upload audio
    with audio_path.open("rb") as audio_file:
        upload_resp = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            data=audio_file,
        )
    upload_resp.raise_for_status()
    upload_url = upload_resp.json()["upload_url"]

    # Start transcription
    payload = {"audio_url": upload_url}
    if model:
        payload["model"] = model
    transcribe_resp = requests.post(
        "https://api.assemblyai.com/v2/transcribe",
        headers=headers,
        json=payload,
    )
    transcribe_resp.raise_for_status()
    job = transcribe_resp.json()
    transcript_id = job["id"]

    status = job["status"]
    while status not in {"completed", "error"}:
        time.sleep(5)
        status_resp = requests.get(
            f"https://api.assemblyai.com/v2/transcribe/{transcript_id}",
            headers=headers,
        )
        status_resp.raise_for_status()
        job = status_resp.json()
        status = job["status"]

    if status == "error":
        raise SystemExit(f"AssemblyAI error: {job.get('error')}")
    return job.get("text", "")


PROVIDERS: dict[str, ProviderFunc] = {
    "openai": openai_transcribe,
    "assembly": assembly_transcribe,
}


def update_request(conn: psycopg.Connection, request_id: str, status: str, text: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE transcription_requests SET status = %s, result_text = %s WHERE id = %s",
            (status, text, request_id),
        )
        conn.commit()


def create_segment_from_transcript(
    conn: psycopg.Connection,
    document_id: str,
    text: str,
    provider: str,
    request_id: str,
    start: float | None,
    end: float | None,
) -> None:
    """Insert a new segment from a transcription result."""
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
            INSERT INTO segments (document_id, text, start_offset, end_offset, provenance, segment_status)
            VALUES (%s, %s, %s, %s, %s, 'proposed')
            """,
            (document_id, text, start_offset, end_offset, Json(provenance)),
        )
        conn.commit()


def run_request(request_id: str) -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit("SUPABASE_DB_URL must be set")

    with psycopg.connect(db_url, autocommit=False) as conn:
        request = fetch_request(conn, request_id)
        provider = request["provider"]
        model = request["model"]
        start = request["start_seconds"]
        end = request["end_seconds"]

        adapter = PROVIDERS.get(provider)
        if not adapter:
            raise SystemExit(f"Unknown provider: {provider}")

        audio_asset = get_audio_asset(request["assets"])
        audio_url = audio_asset.get("url")
        if not audio_url:
            raise SystemExit("Audio URL missing")

        update_request(conn, request_id, "in_progress", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            audio_path = tmpdir_path / "source.mp3"
            download_audio(audio_url, audio_path)

            segment_path = audio_path
            if start or end:
                segment_path = tmpdir_path / "segment.mp3"
                trim_audio(audio_path, segment_path, start, end)

            transcript_text = adapter(segment_path, model)

        create_segment_from_transcript(
            conn,
            document_id=request["document_id"],
            text=transcript_text,
            provider=f"{provider}:{model or ''}",
            request_id=request_id,
            start=start,
            end=end,
        )
        update_request(conn, request_id, "completed", transcript_text)
        print("Transcription completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a transcription request")
    parser.add_argument("request_id", help="ID from transcription_requests")
    args = parser.parse_args()

    run_request(args.request_id)


if __name__ == "__main__":
    from datetime import datetime

    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
