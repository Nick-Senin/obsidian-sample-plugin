import wmill

def main(flow_input, transcribe, **kwargs):
    expected_count = len(flow_input["posts"])
    
    # Берём transcript с fallback на text
    original_text = transcribe.get("transcript", "")
    if not original_text:
        original_text = transcribe.get("text", "")
    
    print(f"DEBUG: Got text of length {len(original_text)}")
    
    max_retries = 3

    for attempt in range(max_retries):
        split_result = wmill.run_script_by_path(
            "f/transformations/post_splitter/split_posts",
            {"input": original_text}
        )

        post_segments = split_result["output"].split("@@@@@")
        actual_count = len([s for s in post_segments if s.strip()])

        if actual_count == expected_count:
            break
        elif attempt < max_retries - 1:
            original_text = f"РАЗБИТЬ НА {expected_count} ПОСТОВ\n\n" + original_text
        else:
            if actual_count > expected_count:
                post_segments = post_segments[:expected_count]
            elif actual_count < expected_count:
                while len([s for s in post_segments if s.strip()]) < expected_count:
                    post_segments.append(post_segments[-1])

    segments = [s.strip() for s in post_segments if s.strip()]
    print(f"DEBUG: Split into {len(segments)} segments")
    return {"segments": segments}
