def main(audio_file=None, posts=None):
    """Проверяет что пришло из prepare_audio"""
    import base64
    
    result = {
        "audio_file_type": str(type(audio_file)),
        "is_list": isinstance(audio_file, list),
        "length": len(audio_file) if isinstance(audio_file, list) else 0,
    }
    
    if isinstance(audio_file, list) and len(audio_file) > 0:
        first = audio_file[0]
        result["first_item_keys"] = list(first.keys()) if isinstance(first, dict) else "not dict"
        result["first_item_name"] = first.get("name") if isinstance(first, dict) else None
        if isinstance(first, dict) and "data" in first:
            data = first["data"]
            result["data_type"] = str(type(data))
            result["data_starts_with"] = data[:50] if isinstance(data, str) else str(data)[:50]
            result["has_data_url_prefix"] = data.startswith("data:audio/mpeg;base64,") if isinstance(data, str) else False
    
    return result
