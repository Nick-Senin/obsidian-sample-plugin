import base64
import os

def main(audio_file=None, recording_path=None, posts=None):
    # Fallback на recording_path
    if audio_file is None and recording_path:
        with open(recording_path, "rb") as f:
            file_data = f.read()
        encoded = base64.b64encode(file_data).decode("utf-8")
        filename = os.path.basename(recording_path)
        audio_file = [{"name": filename, "data": encoded}]

    if audio_file is None:
        raise ValueError("Нужно указать либо audio_file, либо recording_path")

    # Убираем Data URL префикс если есть
    for item in audio_file:
        if isinstance(item, dict) and "data" in item:
            data = item["data"]
            if isinstance(data, str) and data.startswith("data:"):
                item["data"] = data.split(",", 1)[1] if "," in data else data

    return {"audio_file": audio_file, "posts": posts}
