from microclaw.utils.types import Empty


class TestEmpty:
    def test_is_instance_of_itself(self):
        assert isinstance(Empty, Empty)

    def test_call_returns_itself(self):
        assert Empty() is Empty

    def test_not_instance_of_other(self):
        assert not isinstance(object(), Empty)

    def test_not_instance_of_str(self):
        assert not isinstance("hello", Empty)

    def test_not_instance_of_int(self):
        assert not isinstance(42, Empty)
