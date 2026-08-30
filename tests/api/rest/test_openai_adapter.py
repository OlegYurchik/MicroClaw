from microclaw.api.rest.openai.adapter import OpenAIMessageAdapter


class TestOpenAIMessageAdapter:
    def test_to_agent_message_user(self):
        result = OpenAIMessageAdapter.to_agent_message(
            {"role": "user", "content": "hello"}
        )
        assert result.role == "user"
        assert result.text == "hello"

    def test_to_agent_message_system(self):
        result = OpenAIMessageAdapter.to_agent_message(
            {"role": "system", "content": "sys"}
        )
        assert result.role == "system"
        assert result.text == "sys"

    def test_to_agent_message_assistant(self):
        result = OpenAIMessageAdapter.to_agent_message(
            {"role": "assistant", "content": "hi"}
        )
        assert result.role == "assistant"
        assert result.text == "hi"

    def test_to_agent_message_tool(self):
        result = OpenAIMessageAdapter.to_agent_message(
            {"role": "tool", "content": "tool out"}
        )
        assert result.role == "tool"
        assert result.text == "tool out"

    def test_to_agent_message_content_list_extracts_text(self):
        result = OpenAIMessageAdapter.to_agent_message(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "first"},
                    {"type": "image_url", "image_url": {"url": "http://x"}},
                ],
            }
        )
        assert result.role == "user"
        assert result.text == "first"

    def test_to_agent_message_content_list_no_text(self):
        result = OpenAIMessageAdapter.to_agent_message(
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "http://x"}},
                ],
            }
        )
        assert result.role == "user"
        assert result.text == ""

    def test_to_agent_message_default_role(self):
        result = OpenAIMessageAdapter.to_agent_message({"content": "no role"})
        assert result.role == "user"
        assert result.text == "no role"

    def test_to_agent_message_none_content(self):
        result = OpenAIMessageAdapter.to_agent_message({"role": "user"})
        assert result.role == "user"
        assert result.text == ""

    def test_to_agent_message_unknown_role(self):
        result = OpenAIMessageAdapter.to_agent_message(
            {"role": "custom", "content": "x"}
        )
        assert result.role == "user"
        assert result.text == "x"
