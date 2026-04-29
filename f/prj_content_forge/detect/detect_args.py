def main(**kwargs):
    """Показывает все аргументы которые Windmill передаёт"""
    result = []
    result.append(f"Total args: {len(kwargs)}")
    for key, value in kwargs.items():
        value_type = type(value).__name__
        if isinstance(value, dict):
            result.append(f"{key}: dict with keys {list(value.keys())[:5]}")
        elif isinstance(value, list):
            result.append(f"{key}: list with {len(value)} items")
        else:
            result.append(f"{key}: {value_type} = {str(value)[:100]}")
    return {"detected_args": "\n".join(result)}
