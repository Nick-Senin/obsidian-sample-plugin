def main(titles_text: str, analysis_type: str = "") -> dict:
    lines = [ln.strip() for ln in (titles_text or "").splitlines() if ln.strip()]
    title = lines[0] if lines else ""
    if not title:
        title = f"transcript ({analysis_type})" if analysis_type else "transcript"
    return {"title": title}

