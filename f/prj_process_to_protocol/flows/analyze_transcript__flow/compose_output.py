def main(get_transcript, analyze, pick_title=None, paste_transcript=None, send_tg=None, **kwargs):
    return {
        "analysis_type": get_transcript.get("analysis_type"),
        "transcribed_via": get_transcript.get("transcribed_via"),
        "transcript": get_transcript.get("text"),
        "title": (pick_title or {}).get("title"),
        "pastebin_url": (paste_transcript or {}).get("url"),
        "telegram": send_tg,
        "analysis": analyze,
    }
