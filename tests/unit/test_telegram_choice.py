from unittest.mock import patch

import pytest

from f.transformations.human_in_loop import telegram_choice


def test_normalize_string_options():
    result = telegram_choice._normalize_options(["Да", "Нет"])

    assert result == [
        {"label": "Да", "value": "Да", "index": 0},
        {"label": "Нет", "value": "Нет", "index": 1},
    ]


def test_normalize_dict_options_prefers_label_and_keeps_value():
    result = telegram_choice._normalize_options(
        [{"label": "Одобрить", "value": {"action": "approve"}}]
    )

    assert result[0]["label"] == "Одобрить"
    assert result[0]["value"] == {"action": "approve"}
    assert result[0]["index"] == 0


def test_build_inline_keyboard_uses_short_callback_data():
    options = telegram_choice._normalize_options(["Да", "Нет", "Позже"])

    keyboard = telegram_choice._build_inline_keyboard("abc123", options, columns=2)

    assert keyboard == [
        [
            {"text": "Да", "callback_data": "hitl:abc123:0"},
            {"text": "Нет", "callback_data": "hitl:abc123:1"},
        ],
        [{"text": "Позже", "callback_data": "hitl:abc123:2"}],
    ]


def test_polling_rejects_active_webhook_without_delete():
    with patch.object(
        telegram_choice,
        "_telegram_request",
        return_value={"url": "https://example.com/webhook"},
    ):
        with pytest.raises(RuntimeError, match="active webhook"):
            telegram_choice._ensure_polling_allowed("token", delete_webhook_if_set=False)


def test_get_initial_offset_tolerates_polling_conflict():
    with patch.object(
        telegram_choice,
        "_telegram_request",
        side_effect=telegram_choice.TelegramPollingConflict("conflict"),
    ):
        assert telegram_choice._get_initial_offset("token") is None
