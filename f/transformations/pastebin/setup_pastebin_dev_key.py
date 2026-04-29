import wmill


def main(
    dev_key: str,
    variable_path: str = "u/theatmacreator/pastebin_dev_key",
) -> dict:
    """
    SETUP_PASTEBIN_DEV_KEY - сохраняет Pastebin api_dev_key в secret variable Windmill.

    @param dev_key Pastebin api_dev_key
    @param variable_path Путь переменной в Windmill
    """
    if not isinstance(dev_key, str) or not dev_key.strip():
        raise ValueError("dev_key is required")

    if not isinstance(variable_path, str) or not variable_path.strip():
        raise ValueError("variable_path is required")

    # Python SDK принимает только `is_secret` (без auto-create flags/description).
    # Если переменная не существует, она будет создана.
    wmill.set_variable(variable_path.strip(), dev_key.strip(), is_secret=True)

    return {"ok": True, "variable_path": variable_path.strip()}
