import base64
import os
import re
import subprocess
import tempfile
import time
import typing as t
from urllib.parse import urlparse

import requests
import wmill
from imageio_ffmpeg import get_ffmpeg_exe


def _is_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def _safe_int(value: t.Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _decode_possible_base64(value: str) -> bytes | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("data:"):
        parts = text.split(",", 1)
        if len(parts) == 2:
            try:
                return base64.b64decode(parts[1])
            except Exception:
                return None
        return None
    if len(text) < 100:
        return None
    try:
        return base64.b64decode(text, validate=True)
    except Exception:
        return None


def _write_bytes_to_file(content: bytes, suffix: str = ".bin") -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        return tmp.name


def _download_to_file(url: str) -> str:
    parsed = urlparse(url)
    suffix = os.path.splitext(parsed.path or "")[1] or ".bin"
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp.write(chunk)
            return tmp.name


def _coerce_root_job_id(raw: t.Any) -> str | None:
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        for key in ("job_id", "root_job_id", "id", "uuid", "value"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _load_root_flow_args() -> dict[str, t.Any]:
    root_job_id = _coerce_root_job_id(getattr(wmill, "get_root_job_id", lambda *_args, **_kwargs: None)())
    if not root_job_id:
        return {}

    base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
    workspace = os.environ.get("WM_WORKSPACE")
    token = os.environ.get("WM_TOKEN")
    if not base_url or not workspace or not token:
        return {}

    response = requests.get(
        f"{base_url.rstrip('/')}/api/w/{workspace}/jobs_u/get_args/{root_job_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def _materialize_input_audio(audio_url: str | None, audio_file: t.Any) -> tuple[str, str]:
    if isinstance(audio_url, str) and audio_url.strip():
        normalized = audio_url.strip()
        if not _is_url(normalized):
            raise ValueError("audio_url must be a valid URL")
        return _download_to_file(normalized), "audio_url"

    file_obj = audio_file
    if isinstance(file_obj, list) and file_obj:
        file_obj = file_obj[0]

    if isinstance(file_obj, dict):
        s3_path = file_obj.get("s3")
        if isinstance(s3_path, str) and s3_path.strip():
            content = wmill.load_s3_file({"s3": s3_path.strip()})
            if not content:
                raise ValueError("audio_file.s3 exists but content is empty")
            suffix = os.path.splitext(s3_path)[1] or ".bin"
            return _write_bytes_to_file(bytes(content), suffix=suffix), "audio_file_s3"

        data = file_obj.get("data")
        if isinstance(data, (bytes, bytearray)):
            return _write_bytes_to_file(bytes(data), suffix=".bin"), "audio_file_data"
        if isinstance(data, str):
            decoded = _decode_possible_base64(data)
            if decoded:
                return _write_bytes_to_file(decoded, suffix=".bin"), "audio_file_data"

    if isinstance(file_obj, (bytes, bytearray)):
        return _write_bytes_to_file(bytes(file_obj), suffix=".bin"), "audio_file_raw"

    if isinstance(file_obj, str) and file_obj.strip():
        text = file_obj.strip()
        if _is_url(text):
            return _download_to_file(text), "audio_file_url"
        decoded = _decode_possible_base64(text)
        if decoded:
            return _write_bytes_to_file(decoded, suffix=".bin"), "audio_file_data"

    raise ValueError("Provide transcript or audio_url/audio_file")


def _read_duration_seconds(ffmpeg_bin: str, input_path: str) -> float:
    probe = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-i", input_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    text = (probe.stderr or "") + "\n" + (probe.stdout or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError("Unable to read audio duration via ffmpeg")
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _run_ffmpeg_chunk(
    ffmpeg_bin: str,
    input_path: str,
    output_path: str,
    start_seconds: float,
    chunk_seconds: int,
) -> None:
    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_seconds:.3f}",
        "-t",
        str(chunk_seconds),
        "-i",
        input_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        output_path,
    ]
    subprocess.run(command, check=True)


def _merge_text(acc: str, new_part: str) -> str:
    current = acc.strip()
    incoming = new_part.strip()
    if not current:
        return incoming
    if not incoming:
        return current

    tail = current[-320:].lower()
    head = incoming[:320].lower()
    overlap = 0
    max_len = min(len(tail), len(head))
    for size in range(max_len, 24, -1):
        if tail[-size:] == head[:size]:
            overlap = size
            break
    if overlap:
        incoming = incoming[overlap:].lstrip()
    return (current + "\n" + incoming).strip()


def _run_transcriber(
    script_path: str,
    audio_file_value: t.Any,
    audio_url_value: str | None,
    retries: int,
    poll_interval: int,
    max_wait_time: int,
) -> dict[str, t.Any]:
    attempt = 0
    while True:
        try:
            args: dict[str, t.Any] = {
                "audio_file": audio_file_value,
                "audio_url": audio_url_value,
            }
            # GigaAM script accepts polling controls; Deepgram does not.
            if script_path.endswith("/gigaam_transcriber/transcribe"):
                args["poll_interval"] = poll_interval
                args["max_wait_time"] = max_wait_time
            return wmill.run_script_by_path(
                script_path,
                args,
            )
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(2**attempt)
            attempt += 1


def main(
    payload: dict[str, t.Any] | None = None,
    analysis_type: str | None = None,
    transcript: str | None = None,
    audio_url: str | None = None,
    audio_file: t.Any = None,
    chunk_minutes: int = 15,
    overlap_seconds: int = 10,
    transcriber_script_path: str = "f/transformations/gigaam_transcriber/transcribe",
    audio_url_fallback_transcriber_script_path: str = "f/transformations/transcriber/transcribe",
    chunk_fallback_transcriber_script_path: str = "f/transformations/transcriber/transcribe",
    allow_chunk_fallback_for_audio_url: bool = False,
    transcriber_retries: int = 2,
    s3_prefix: str = "tmp/chunked_transcript",
    poll_interval: int = 5,
    max_wait_time: int = 86400,
) -> dict[str, t.Any]:
    """
    Подготовительный шаг:
    - если transcript уже передан, возвращает его как есть;
    - если есть аудио, режет на фиксированные куски и транскрибирует по одному;
    - складывает чанки в S3 (если недоступно, использует inline base64 fallback);
    - возвращает объединенный текст + информацию о пропусках.
    """
    payload = payload or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    if transcript is None:
        transcript = payload.get("transcript")
    if analysis_type is None:
        analysis_type = payload.get("analysis_type")
    if audio_url is None:
        audio_url = payload.get("audio_url")
    if audio_file is None:
        audio_file = payload.get("audio_file")

    if analysis_type is None and transcript is None and audio_url is None and audio_file is None:
        root_args = _load_root_flow_args()
        if analysis_type is None:
            analysis_type = root_args.get("analysis_type")
        if transcript is None:
            transcript = root_args.get("transcript")
        if audio_url is None:
            audio_url = root_args.get("audio_url")
        if audio_file is None:
            audio_file = root_args.get("audio_file")

    if isinstance(transcript, str) and transcript.strip() and not (audio_url or audio_file):
        return {
            "analysis_type": analysis_type,
            "transcript": transcript.strip(),
            "audio_url": None,
            "audio_file": None,
            "warning": None,
            "missing_parts": [],
            "stats": {
                "mode": "pass_through_transcript",
                "chunks_total": 0,
                "chunks_success": 0,
                "chunks_failed": 0,
            },
        }

    if not audio_url and not audio_file:
        return {
            "analysis_type": analysis_type,
            "transcript": transcript.strip() if isinstance(transcript, str) else None,
            "audio_url": None,
            "audio_file": None,
            "warning": "No audio provided; transcript may be empty",
            "missing_parts": [],
            "stats": {
                "mode": "no_audio",
                "chunks_total": 0,
                "chunks_success": 0,
                "chunks_failed": 0,
            },
        }

    chunk_seconds = max(60, _safe_int(chunk_minutes, 15) * 60)
    overlap_seconds = max(0, _safe_int(overlap_seconds, 10))
    if overlap_seconds >= chunk_seconds:
        raise ValueError("overlap_seconds must be smaller than chunk size")
    step_seconds = chunk_seconds - overlap_seconds
    transcriber_retries = max(0, _safe_int(transcriber_retries, 2))
    poll_interval = max(1, _safe_int(poll_interval, 5))
    max_wait_time = max(60, _safe_int(max_wait_time, 86400))

    # Для публичного audio_url используем прямую транскрибацию без нарезки.
    # Chunked-mode по URL часто нестабилен из-за file-upload на стороне backend.
    if isinstance(audio_url, str) and audio_url.strip() and not audio_file:
        normalized_url = audio_url.strip()
        errors: list[str] = []

        def _try_direct(path: str) -> dict[str, t.Any] | None:
            try:
                direct_result = _run_transcriber(
                    script_path=path,
                    audio_file_value=None,
                    audio_url_value=normalized_url,
                    retries=transcriber_retries,
                    poll_interval=poll_interval,
                    max_wait_time=max_wait_time,
                )
                direct_text = ((direct_result or {}).get("text") or "").strip()
                if not direct_text:
                    errors.append(f"{path}: empty transcript")
                    return None

                return {
                    "analysis_type": analysis_type,
                    "transcript": direct_text,
                    # Transcript is already produced here, so downstream steps
                    # should consume text directly instead of re-transcribing.
                    "audio_url": None,
                    "audio_file": None,
                    "warning": None,
                    "missing_parts": [],
                    "stats": {
                        "mode": "direct_audio_url",
                        "source_mode": "audio_url",
                        "transcriber_script_path": path,
                        "chunks_total": 1,
                        "chunks_success": 1,
                        "chunks_failed": 0,
                    },
                    "chunks": [
                        {
                            "chunk_index": 0,
                            "start_seconds": 0,
                            "end_seconds": None,
                            "status": "ok",
                            "transcribe_job_id": (direct_result or {}).get("job_id"),
                            "took_seconds": (direct_result or {}).get("took_seconds"),
                            "storage_mode": "url_direct",
                            "text_len": len(direct_text),
                        }
                    ],
                }
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path}: {exc}")
                return None

        direct_primary = _try_direct(transcriber_script_path)
        if direct_primary:
            return direct_primary

        if (
            audio_url_fallback_transcriber_script_path
            and audio_url_fallback_transcriber_script_path != transcriber_script_path
        ):
            direct_secondary = _try_direct(audio_url_fallback_transcriber_script_path)
            if direct_secondary:
                return direct_secondary

        if not allow_chunk_fallback_for_audio_url:
            # Let downstream orchestration decide how to transcribe audio_url.
            return {
                "analysis_type": analysis_type,
                "transcript": transcript.strip() if isinstance(transcript, str) and transcript.strip() else None,
                "audio_url": normalized_url,
                "audio_file": None,
                "warning": (
                    "Direct audio_url transcription failed in prepare_transcript; "
                    "passing audio_url downstream. " + " | ".join(errors[:3])
                ),
                "missing_parts": [],
                "stats": {
                    "mode": "audio_url_passthrough_after_direct_failure",
                    "source_mode": "audio_url",
                    "transcriber_script_path": None,
                    "chunks_total": 0,
                    "chunks_success": 0,
                    "chunks_failed": 0,
                },
                "chunks": [],
            }

    ffmpeg_bin = get_ffmpeg_exe()
    source_path, source_mode = _materialize_input_audio(
        audio_url=audio_url if isinstance(audio_url, str) else None,
        audio_file=audio_file,
    )

    temp_dir = tempfile.mkdtemp(prefix="wm_chunked_audio_")
    missing_parts: list[dict[str, t.Any]] = []
    chunk_rows: list[dict[str, t.Any]] = []
    merged_text = ""
    chunk_success = 0
    chunk_fallback_success = 0
    chunk_total = 0

    try:
        duration_seconds = _read_duration_seconds(ffmpeg_bin, source_path)
        if duration_seconds <= 0:
            raise ValueError("Audio duration must be positive")

        run_id = os.getenv("WM_JOB_ID", f"local-{int(time.time())}")
        prefix = (s3_prefix or "tmp/chunked_transcript").strip("/")

        chunk_index = 0
        start = 0.0
        while start < duration_seconds:
            end = min(duration_seconds, start + chunk_seconds)
            out_path = os.path.join(temp_dir, f"chunk_{chunk_index:04d}.mp3")
            _run_ffmpeg_chunk(
                ffmpeg_bin=ffmpeg_bin,
                input_path=source_path,
                output_path=out_path,
                start_seconds=start,
                chunk_seconds=max(1, int(end - start)),
            )
            if not os.path.exists(out_path) or os.path.getsize(out_path) < 1024:
                break

            chunk_total += 1
            s3_obj = {"s3": f"{prefix}/{run_id}/chunk_{chunk_index:04d}.mp3"}

            row: dict[str, t.Any] = {
                "chunk_index": chunk_index,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "status": "failed",
            }
            transcribe_audio_input: t.Any
            transcribe_audio_url: str | None = None

            try:
                with open(out_path, "rb") as reader:
                    saved = wmill.write_s3_file(s3_obj, reader)
                row["chunk_s3"] = (saved or {}).get("s3", s3_obj["s3"])
                # Для chunked-режима URL-режим в транскрибере стабильнее, чем file upload.
                try:
                    transcribe_audio_url = wmill.get_presigned_s3_public_url({"s3": row["chunk_s3"]})
                except Exception as presign_exc:  # noqa: BLE001
                    row["presign_error"] = str(presign_exc)
                    transcribe_audio_url = None

                if transcribe_audio_url:
                    row["storage_mode"] = "s3_presigned_url"
                    row["chunk_url"] = transcribe_audio_url
                    transcribe_audio_input = None
                else:
                    row["storage_mode"] = "s3"
                    transcribe_audio_input = {"s3": row["chunk_s3"]}
            except Exception as storage_exc:  # noqa: BLE001
                with open(out_path, "rb") as reader:
                    encoded = base64.b64encode(reader.read()).decode("ascii")
                row["chunk_s3"] = None
                row["storage_mode"] = "inline_base64_fallback"
                row["storage_error"] = str(storage_exc)
                transcribe_audio_input = [{"name": f"chunk_{chunk_index:04d}.mp3", "data": encoded}]
                transcribe_audio_url = None

            transcribe_result: dict[str, t.Any] | None = None
            text = ""
            used_script_path = transcriber_script_path
            primary_error: str | None = None
            fallback_error: str | None = None
            used_fallback = False

            try:
                transcribe_result = _run_transcriber(
                    script_path=transcriber_script_path,
                    audio_file_value=transcribe_audio_input,
                    audio_url_value=transcribe_audio_url,
                    retries=transcriber_retries,
                    poll_interval=poll_interval,
                    max_wait_time=max_wait_time,
                )
                text = ((transcribe_result or {}).get("text") or "").strip()
                if not text:
                    primary_error = "empty_transcript"
            except Exception as exc:  # noqa: BLE001
                primary_error = str(exc)

            if (
                not text
                and chunk_fallback_transcriber_script_path
                and chunk_fallback_transcriber_script_path != transcriber_script_path
            ):
                try:
                    fallback_result = _run_transcriber(
                        script_path=chunk_fallback_transcriber_script_path,
                        audio_file_value=transcribe_audio_input,
                        audio_url_value=transcribe_audio_url,
                        retries=transcriber_retries,
                        poll_interval=poll_interval,
                        max_wait_time=max_wait_time,
                    )
                    fallback_text = ((fallback_result or {}).get("text") or "").strip()
                    if fallback_text:
                        transcribe_result = fallback_result
                        text = fallback_text
                        used_script_path = chunk_fallback_transcriber_script_path
                        used_fallback = True
                    else:
                        fallback_error = "empty_transcript"
                except Exception as fallback_exc:  # noqa: BLE001
                    fallback_error = str(fallback_exc)

            row["transcriber_script_path"] = used_script_path
            row["transcribe_job_id"] = (transcribe_result or {}).get("job_id")
            row["took_seconds"] = (transcribe_result or {}).get("took_seconds")

            if text:
                merged_text = _merge_text(merged_text, text)
                chunk_success += 1
                if used_fallback:
                    chunk_fallback_success += 1
                    row["status"] = "ok_fallback"
                    row["fallback_used"] = True
                else:
                    row["status"] = "ok"
                    row["fallback_used"] = False
                row["text_len"] = len(text)
            else:
                if primary_error and fallback_error:
                    error_text = f"primary={primary_error}; fallback={fallback_error}"
                else:
                    error_text = primary_error or fallback_error or "empty_transcript"
                row["error"] = error_text
                missing_parts.append(
                    {
                        "chunk_index": chunk_index,
                        "start_seconds": row["start_seconds"],
                        "end_seconds": row["end_seconds"],
                        "error": error_text,
                    }
                )

            chunk_rows.append(row)
            chunk_index += 1
            start += step_seconds

        warning: str | None = None
        if missing_parts:
            ranges = ", ".join(
                f"#{p['chunk_index']}({int(p['start_seconds'])}-{int(p['end_seconds'])}s)"
                for p in missing_parts[:12]
            )
            warning = (
                f"Transcript is partial: missing {len(missing_parts)} chunk(s). "
                f"Missing ranges: {ranges}"
            )
            if merged_text:
                merged_text = f"{merged_text}\n\n[WARNING] {warning}"

        if not merged_text.strip():
            raise ValueError(
                "No transcript text produced from chunks. "
                f"Failed chunks: {len(missing_parts)} / {chunk_total}"
            )

        return {
            "analysis_type": analysis_type,
            "transcript": merged_text.strip(),
            "audio_url": None,
            "audio_file": None,
            "warning": warning,
            "missing_parts": missing_parts,
            "stats": {
                "mode": "chunked_audio",
                "source_mode": source_mode,
                "duration_seconds": round(duration_seconds, 3),
                "chunk_minutes": chunk_seconds / 60,
                "overlap_seconds": overlap_seconds,
                "chunks_total": chunk_total,
                "chunks_success": chunk_success,
                "chunks_failed": chunk_total - chunk_success,
                "chunks_fallback_success": chunk_fallback_success,
            },
            "chunks": chunk_rows,
        }
    finally:
        if os.path.exists(source_path):
            os.remove(source_path)
        if os.path.isdir(temp_dir):
            for name in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(temp_dir)
