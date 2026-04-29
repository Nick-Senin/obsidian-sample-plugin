import base64
import os

def main(audio_file=None, posts=None, flow_input=None, recording_path=None, **kwargs):
    """Подготавливает аудиофайл для транскрибации"""
    print(f"DEBUG: audio_file type: {type(audio_file)}")
    print(f"DEBUG: audio_file is None: {audio_file is None}")
    print(f"DEBUG: posts type: {type(posts)}")
    print(f"DEBUG: flow_input type: {type(flow_input)}")
    print(f"DEBUG: kwargs keys: {list(kwargs.keys())}")
    
    # Если audio_file не передан напрямую, пробуем из flow_input
    if not audio_file and flow_input:
        audio_file = flow_input.get("audio_file")
        posts = flow_input.get("posts", posts)
        print(f"DEBUG: Got audio_file from flow_input")
    
    # Проверяем что audio_file не пустой
    if not audio_file or (isinstance(audio_file, list) and len(audio_file) == 0):
        raise ValueError(f"audio_file is required. Got: {audio_file}")
    
    print(f"DEBUG: Returning audio_file with {len(audio_file) if isinstance(audio_file, list) else 1} files")
    return {"audio_file": audio_file, "posts": posts or []}
