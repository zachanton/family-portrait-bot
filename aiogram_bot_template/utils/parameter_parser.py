# File: aiogram_bot_template/utils/parameter_parser.py

import json
from typing import Any


def extract_latest_parameters(raw_params: Any) -> dict[str, Any]:
    """
    Safely extracts the most recent parameter dictionary from a database field.

    This function is designed to be robust against various data formats that may
    exist in the `request_parameters` JSONB column, such as:
    - A single JSON object (dict).
    - A JSON array containing multiple objects or JSON strings (list).
    - A single JSON string.
    - None or other invalid types.

    It iterates through a list in reverse to find the last valid dictionary,
    ensuring that the most recent set of parameters is always used.

    Args:
        raw_params: The raw value from the database.

    Returns:
        The latest valid parameter dictionary found, or an empty dictionary.
    """
    if not raw_params:
        return {}

    if isinstance(raw_params, dict):
        return raw_params

    if isinstance(raw_params, str):
        try:
            data = json.loads(raw_params)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    if isinstance(raw_params, list):
        for item in reversed(raw_params):
            if isinstance(item, dict) and item:
                return item
            if isinstance(item, str):
                try:
                    data = json.loads(item)
                    if isinstance(data, dict) and data:
                        return data
                except json.JSONDecodeError:
                    continue

    return {}
