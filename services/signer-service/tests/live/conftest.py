import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    if os.getenv("HONGGUO_RUN_LIVE_TESTS") == "1":
        return
    marker = pytest.mark.skip(reason="set HONGGUO_RUN_LIVE_TESTS=1")
    for item in items:
        if "/tests/live/" in str(item.path).replace("\\", "/"):
            item.add_marker(marker)
