import uuid

from microclaw.utils.context import (
    get_current_request_id,
    get_current_session_id,
    set_current_request_id,
    set_current_session_id,
)


def test_get_current_request_id_default():
    assert get_current_request_id() is None


def test_get_current_session_id_default():
    assert get_current_session_id() is None


def test_set_current_request_id():
    request_id = uuid.uuid4()
    assert get_current_request_id() is None
    with set_current_request_id(request_id):
        assert get_current_request_id() == request_id
    assert get_current_request_id() is None


def test_set_current_session_id():
    session_id = uuid.uuid4()
    assert get_current_session_id() is None
    with set_current_session_id(session_id):
        assert get_current_session_id() == session_id
    assert get_current_session_id() is None
