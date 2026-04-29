"""
SELECT_CONFIG - выбор конфигурации поста по индексу

ЧТО ДЕЛАЕТ:
- Выбирает конфигурацию из массива posts по текущему индексу итерации
- Если индекс превышает длину массива, использует последний элемент

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/process_recording (forloopflow)

ИСПОЛЬЗУЕТ:
- Flow input: flow_input.iter.index, flow_input.posts
"""
def main(index, posts, **kwargs):
    """
    Выбирает конфигурацию по индексу с fallback на последний.

    @param index Индекс текущей итерации
    @param posts Массив конфигураций [{channel_id, channel_name, genre_id, genre_name, date}]
    @return Выбранная конфигурация
    """
    config = posts[index] if index < len(posts) else posts[-1]
    return {
        "channel_id": config["channel_id"],
        "channel_name": config["channel_name"],
        "genre_id": config["genre_id"],
        "genre_name": config["genre_name"],
        "date": config["date"]
    }
