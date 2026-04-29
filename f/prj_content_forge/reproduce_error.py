"""
Воспроизводит ошибку из flow:
ValueError: Нужно указать либо audio_file, либо recording_path

Этот скрипт симулирует поведение rawscript внутри flow,
где аргументы не маппятся правильно.
"""
import base64

def main(audio_file=None, posts=None, recording_path=None):
    """
    Оригинальный код из flow prepare_audio (упрощённый)
    """
    
    print("=" * 60)
    print("REPRODUCING FLOW ERROR")
    print("=" * 60)
    print(f"audio_file: {audio_file}")
    print(f"posts: {posts}")
    print(f"recording_path: {recording_path}")
    print("=" * 60)
    
    # Это код из оригинального prepare_audio в flow
    # Внутри flow audio_file и recording_path оба None!
    if audio_file is None and recording_path is None:
        raise ValueError("Нужно указать либо audio_file, либо recording_path")
    
    # Если бы audio_file был передан:
    return {"audio_file": audio_file, "posts": posts}

