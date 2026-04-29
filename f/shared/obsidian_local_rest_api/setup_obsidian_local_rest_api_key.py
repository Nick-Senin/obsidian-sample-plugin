import wmill


def main(
    api_key: str,
    variable_path: str = "u/theatmacreator/obsidian_local_rest_api_key",
) -> dict:
    """
    SETUP_OBSIDIAN_LOCAL_REST_API_KEY - сохраняет Obsidian Local REST API key в secret variable Windmill.

    @param api_key API key из Obsidian plugin "Local REST API" (не вставляй его в git)
    @param variable_path Путь переменной в Windmill
    """
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("api_key is required")

    if not isinstance(variable_path, str) or not variable_path.strip():
        raise ValueError("variable_path is required")

    # Создаст переменную если её нет, и обновит значение, помечая как secret.
    wmill.set_variable(variable_path.strip(), api_key.strip(), is_secret=True)

    return {"ok": True, "variable_path": variable_path.strip()}

