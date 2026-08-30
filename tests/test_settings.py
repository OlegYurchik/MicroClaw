import pytest

from microclaw.agents import APITypeEnum, InputTypeEnum
from microclaw.agents.settings import (
    AgentSettings,
    ModelSettings,
    ProviderSettings,
)
from microclaw.settings import MicroclawSettings


class TestValidateModelProvider:
    def test_model_provider_not_exists_raises(self):
        with pytest.raises(ValueError, match="Provider for model"):
            MicroclawSettings(
                models={
                    "test_model": ModelSettings(
                        id="gpt-4",
                        provider="nonexistent",
                    )
                }
            )

    def test_model_provider_resolved_from_settings(self):
        settings = MicroclawSettings(
            providers={
                "openai": ProviderSettings(
                    base_url="https://api.openai.com/v1",
                    api_type=APITypeEnum.OPENAI,
                )
            },
            models={
                "test_model": ModelSettings(
                    id="gpt-4",
                    provider="openai",
                )
            },
        )
        assert isinstance(settings.models["test_model"].provider, ProviderSettings)


class TestValidateAgentModel:
    def test_agent_model_not_exists_raises(self):
        with pytest.raises(ValueError, match="Model for agent"):
            MicroclawSettings(
                agents={
                    "test_agent": AgentSettings(
                        model="nonexistent",
                    )
                }
            )

    def test_agent_model_no_text_input_raises(self):
        with pytest.raises(ValueError, match="does not support text input"):
            MicroclawSettings(
                models={
                    "audio_model": ModelSettings(
                        id="whisper",
                        input_types=[InputTypeEnum.AUDIO],
                    )
                },
                agents={
                    "test_agent": AgentSettings(
                        model="audio_model",
                    )
                },
            )

    def test_agent_model_resolved_successfully(self):
        settings = MicroclawSettings(
            models={
                "text_model": ModelSettings(
                    id="gpt-4",
                    input_types=[InputTypeEnum.TEXT],
                )
            },
            agents={
                "test_agent": AgentSettings(
                    model="text_model",
                )
            },
        )
        assert settings.agents["test_agent"].model.id == "gpt-4"


class TestValidateAgentToolkit:
    def test_agent_toolkit_not_found_raises(self):
        with pytest.raises(ValueError, match="toolkit 'unknown'"):
            MicroclawSettings(
                models={
                    "default": ModelSettings(id="gpt-4"),
                },
                agents={
                    "test_agent": AgentSettings(
                        model="default",
                        toolkits=["unknown"],
                    )
                },
            )

    def test_agent_toolkit_dotted_path_allowed(self):
        settings = MicroclawSettings(
            models={
                "default": ModelSettings(id="gpt-4"),
            },
            agents={
                "test_agent": AgentSettings(
                    model="default",
                    toolkits=["some.module.ToolKit"],
                )
            },
        )
        assert settings.agents["test_agent"].toolkits == ["some.module.ToolKit"]


class TestValidateChannel:
    def test_channel_agent_not_exists_raises(self):
        with pytest.raises(ValueError, match="Agent 'unknown' for channel"):
            MicroclawSettings(
                channels={
                    "telegram": {
                        "type": "telegram",
                        "agent": "unknown",
                        "token": "test",
                    }
                }
            )

    def test_channel_sessions_storage_not_exists_raises(self):
        with pytest.raises(ValueError, match="Sessions storage 'unknown'"):
            MicroclawSettings(
                channels={
                    "telegram": {
                        "type": "telegram",
                        "sessions_storage": "unknown",
                        "token": "test",
                    }
                }
            )

    def test_channel_users_storage_not_exists_raises(self):
        with pytest.raises(ValueError, match="Users storage 'unknown'"):
            MicroclawSettings(
                channels={
                    "telegram": {
                        "type": "telegram",
                        "users_storage": "unknown",
                        "token": "test",
                    }
                }
            )


class TestValidateDuplicateNames:
    def test_duplicate_mcp_names_raises(self):
        from microclaw.agents.settings import MCPRemoteSettings

        with pytest.raises(ValueError, match="unique names"):
            MicroclawSettings(
                mcp={
                    "mcp1": MCPRemoteSettings(name="same", url="http://a"),
                    "mcp2": MCPRemoteSettings(name="same", url="http://b"),
                }
            )


class TestLoad:
    def test_load_from_config_file(self, tmp_path):
        config = tmp_path / "config.yaml"
        config.write_text("""
logging:
  level: DEBUG
""")
        settings = MicroclawSettings.load(config_file=config)
        assert settings.logging.level == "DEBUG"

    def test_load_env_prefix(self, tmp_path):
        config = tmp_path / "config.yaml"
        config.write_text("logging:\n  level: INFO\n")
        settings = MicroclawSettings.load(
            config_file=config,
            env_prefix="MICROCLAW__",
        )
        assert settings.logging.level == "INFO"

    def test_load_with_include(self, tmp_path):
        include_file = tmp_path / "included.yaml"
        include_file.write_text("level: ERROR\n")

        config = tmp_path / "config.yaml"
        config.write_text(f"""
logging:
  !include {include_file.name}
""")
        settings = MicroclawSettings.load(config_file=config)
        assert settings.logging.level == "ERROR"

    def test_stt_model_no_audio_input_raises(self):
        from microclaw.stt import STTSettings

        with pytest.raises(ValueError, match="does not support audio input"):
            MicroclawSettings(
                models={
                    "text_model": ModelSettings(
                        id="gpt-4", input_types=[InputTypeEnum.TEXT]
                    ),
                },
                stt={"default": STTSettings(model="text_model")},
            )

    def test_duplicate_toolkit_names_raises(self):
        from microclaw.toolkits import ToolKitSettings

        with pytest.raises(ValueError, match="unique names"):
            MicroclawSettings(
                models={"default": ModelSettings(id="gpt-4")},
                toolkits={
                    "tk1": ToolKitSettings(path="a.b", name="same"),
                    "tk2": ToolKitSettings(path="c.d", name="same"),
                },
            )

    def test_skill_repo_not_defined_raises(self):
        from microclaw.skills import SkillSettings

        with pytest.raises(ValueError, match="not defined in skills_repositories"):
            MicroclawSettings(
                models={"default": ModelSettings(id="gpt-4")},
                skills={
                    "my-skill": SkillSettings(name="my-skill", repo="missing_repo")
                },
            )

    def test_channel_agent_none_no_agents_raises(self):
        with pytest.raises(ValueError, match="No agents defined"):
            MicroclawSettings(
                agents={},
                channels={
                    "telegram": {
                        "type": "telegram",
                        "token": "test",
                    }
                },
            )

    def test_channel_sessions_storage_none_no_storages_raises(self):
        with pytest.raises(ValueError, match="No sessions storages defined"):
            MicroclawSettings(
                sessions_storages={},
                channels={
                    "telegram": {
                        "type": "telegram",
                        "token": "test",
                    }
                },
            )

    def test_channel_users_storage_none_no_storages_raises(self):
        with pytest.raises(ValueError, match="No users storages defined"):
            MicroclawSettings(
                users_storages={},
                channels={
                    "telegram": {
                        "type": "telegram",
                        "token": "test",
                    }
                },
            )

    def test_channel_stt_inline_no_audio_raises(self):
        with pytest.raises(ValueError, match="does not support audio input"):
            MicroclawSettings(
                models={
                    "text_model": ModelSettings(
                        id="gpt-4", input_types=[InputTypeEnum.TEXT]
                    ),
                },
                channels={
                    "telegram": {
                        "type": "telegram",
                        "token": "test",
                        "stt": {"model": "text_model"},
                    }
                },
            )

    def test_stt_model_not_exists_raises(self):
        from microclaw.stt import STTSettings

        with pytest.raises(ValueError, match="Model for stt"):
            MicroclawSettings(stt={"default": STTSettings(model="missing_model")})

    def test_agent_skill_repo_not_defined_raises(self):
        from microclaw.skills import SkillSettings

        with pytest.raises(ValueError, match="not defined in skills_repositories"):
            MicroclawSettings(
                models={"default": ModelSettings(id="gpt-4")},
                agents={
                    "test_agent": AgentSettings(
                        model="default",
                        skills=[SkillSettings(name="skill", repo="missing")],
                    )
                },
            )
