import time
import typing as t

import requests
import wmill


MODAL_BASE_URL = "https://nick-senin--gigaam-v3-asr-api.modal.run"
DEFAULT_ANALYSIS_TYPE = "обычный"


def _transcribe_audio_url_direct(
    audio_url: str,
    modal_base_url: str = MODAL_BASE_URL,
    poll_interval: int = 5,
    max_wait_time: int = 86400,
    submit_timeout: int = 180,
) -> dict:
    submit_url = f"{modal_base_url.rstrip('/')}/full/submit"
    result_url_prefix = f"{modal_base_url.rstrip('/')}/full/result"

    try:
        submit_response = requests.post(
            submit_url,
            data={"url": audio_url},
            timeout=submit_timeout,
        )
        submit_response.raise_for_status()
        submit_result = submit_response.json()
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"Failed to submit audio_url to GigaAM: {exc}")

    job_id = submit_result.get("job_id")
    if not job_id:
        raise ValueError("GigaAM did not return job_id")

    started_at = time.time()
    while True:
        if time.time() - started_at > max_wait_time:
            raise ValueError(f"GigaAM transcription timed out after {max_wait_time} seconds")

        try:
            result_response = requests.get(f"{result_url_prefix}/{job_id}", timeout=30)
            result_response.raise_for_status()
            result = result_response.json()
        except requests.exceptions.RequestException:
            time.sleep(poll_interval)
            continue

        status = result.get("status")
        if status == "done":
            text = (result.get("text") or "").strip()
            if not text:
                raise ValueError("GigaAM direct audio_url returned empty text")
            return {
                "text": text,
                "mode": result.get("mode", "full"),
                "model_repo": result.get("model_repo"),
                "revision": result.get("revision"),
                "audio_seconds": result.get("audio_seconds"),
                "took_seconds": result.get("took_seconds"),
                "chunks": result.get("chunks"),
                "job_id": job_id,
                "full_result": result,
            }
        if "error" in result:
            raise ValueError(f"GigaAM direct audio_url failed: {result.get('message', result.get('error'))}")

        time.sleep(poll_interval)


def main(
    analysis_type: str | None = None,
    transcript: str | None = None,
    audio_file: t.Any | None = None,
    audio_url: str | None = None,
    **kwargs,
) -> dict:
    """
    Унифицирует вход:
    - Если есть аудио (audio_file/audio_url) — делает транскрибацию через GigaAM.
    - Иначе использует переданный transcript как готовый текст.
    """
    analysis_type_value = (
        analysis_type.strip()
        if isinstance(analysis_type, str) and analysis_type.strip()
        else DEFAULT_ANALYSIS_TYPE
    )

    has_audio_url = isinstance(audio_url, str) and audio_url.strip()
    has_audio_file = audio_file is not None and audio_file != []

    if has_audio_url:
        result = _transcribe_audio_url_direct(audio_url.strip())
        text = (result or {}).get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("gigaam_transcriber returned empty text")
        return {
            "analysis_type": analysis_type_value,
            "text": text.strip(),
            "transcribed_via": "gigaam",
            "transcription_result": result,
        }

    if has_audio_file:
        result = wmill.run_script_by_path(
            "f/transformations/gigaam_transcriber/transcribe",
            {
                "audio_file": audio_file,
                "audio_url": None,
            },
        )
        text = (result or {}).get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("gigaam_transcriber returned empty text")
        return {
            "analysis_type": analysis_type_value,
            "text": text.strip(),
            "transcribed_via": "gigaam",
            "transcription_result": result,
        }

    if isinstance(transcript, str) and transcript.strip():
        return {
            "analysis_type": analysis_type_value,
            "text": transcript.strip(),
            "transcribed_via": "provided",
            "transcription_result": None,
        }

    raise ValueError("Provide either transcript (string) or audio_file/audio_url for GigaAM transcription")
