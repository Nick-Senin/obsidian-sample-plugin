def main(flow_input, process_posts, **kwargs):
    """
    Агрегирует результаты обработки постов из forloopflow.
    process_posts - это список результатов от process_single_post для каждого сегмента.
    """
    # process_posts уже содержит список результатов
    results_list = process_posts if isinstance(process_posts, list) else []

    return {
        "status": "success",
        "posts_processed": len(results_list),
        "results": results_list
    }
