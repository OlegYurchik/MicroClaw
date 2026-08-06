"""Test that all concrete channels implement BaseChannel API correctly."""

import inspect

import pytest

from microclaw.channels.base import BaseChannel


@pytest.mark.parametrize(
    "channel_cls",
    [
        pytest.param(
            "microclaw.channels.telegram.base.BaseTelegramChannel",
            id="telegram",
        ),
        pytest.param(
            "microclaw.channels.vk.base.BaseVKChannel",
            id="vk",
        ),
        pytest.param(
            "microclaw.channels.tui.channel.TUIChannel",
            id="tui",
        ),
    ],
)
def test_process_batch_signature_matches_base(channel_cls: str):
    """Ensure _process_batch override accepts keyword args from _enqueue_and_process."""
    mod_path, cls_name = channel_cls.rsplit(".", 1)
    module = __import__(mod_path, fromlist=[cls_name])
    cls = getattr(module, cls_name)

    base_sig = inspect.signature(BaseChannel._process_batch)
    override_sig = inspect.signature(cls._process_batch)

    # All keyword args from base must be present in override
    for param_name in base_sig.parameters:
        if param_name == "self":
            continue
        assert (
            param_name in override_sig.parameters
        ), f"{channel_cls}._process_batch missing parameter '{param_name}'"


@pytest.mark.parametrize(
    "channel_cls",
    [
        pytest.param(
            "microclaw.channels.telegram.base.BaseTelegramChannel",
            id="telegram",
        ),
        pytest.param(
            "microclaw.channels.vk.base.BaseVKChannel",
            id="vk",
        ),
        pytest.param(
            "microclaw.channels.tui.channel.TUIChannel",
            id="tui",
        ),
    ],
)
def test_resolve_session_for_chat_signature_matches_base(channel_cls: str):
    """Ensure _resolve_session_for_chat override accepts keyword args."""
    mod_path, cls_name = channel_cls.rsplit(".", 1)
    module = __import__(mod_path, fromlist=[cls_name])
    cls = getattr(module, cls_name)

    base_sig = inspect.signature(BaseChannel._resolve_session_for_chat)
    override_sig = inspect.signature(cls._resolve_session_for_chat)

    for param_name in base_sig.parameters:
        if param_name == "self":
            continue
        assert (
            param_name in override_sig.parameters
        ), f"{channel_cls}._resolve_session_for_chat missing parameter '{param_name}'"
