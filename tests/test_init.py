"""Tests for the init wizard (_init_wizard)."""

from pathlib import Path
from unittest.mock import patch, MagicMock



class TestInitWizard:
    """Tests for main._init_wizard() with mocked I/O."""

    def test_saves_zotero_credentials(self, tmp_path, monkeypatch):
        from distillate import config

        env_file = tmp_path / ".env"
        monkeypatch.setattr(config, "ENV_PATH", env_file)

        inputs = iter([
            "test_api_key",     # Zotero API key
            "12345",            # Zotero user ID
            "n",                # Skip reMarkable registration
            "3",                # Skip output
            "",                 # Skip Anthropic key
            "",                 # Skip Resend key
        ])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("builtins.input", lambda _: next(inputs)), \
             patch("requests.get", return_value=mock_resp):
            from distillate.main import _init_wizard
            _init_wizard()

        text = env_file.read_text()
        assert "ZOTERO_API_KEY=test_api_key" in text
        assert "ZOTERO_USER_ID=12345" in text

    def test_empty_api_key_aborts(self, capsys):
        inputs = iter([""])  # Empty API key
        with patch("builtins.input", lambda _: next(inputs)):
            from distillate.main import _init_wizard
            _init_wizard()

        output = capsys.readouterr().out
        assert "required" in output.lower()

    def test_obsidian_vault_path_saved(self, tmp_path, monkeypatch):
        from distillate import config

        env_file = tmp_path / ".env"
        monkeypatch.setattr(config, "ENV_PATH", env_file)

        vault_path = str(tmp_path / "my_vault")
        inputs = iter([
            "key",              # API key
            "999",              # User ID
            "n",                # Skip reMarkable
            "1",                # Obsidian
            vault_path,         # Vault path
            "",                 # Skip Anthropic
            "",                 # Skip Resend
        ])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("builtins.input", lambda _: next(inputs)), \
             patch("requests.get", return_value=mock_resp):
            from distillate.main import _init_wizard
            _init_wizard()

        text = env_file.read_text()
        assert "OBSIDIAN_VAULT_PATH=" in text

    def test_plain_folder_path_saved(self, tmp_path, monkeypatch):
        from distillate import config

        env_file = tmp_path / ".env"
        monkeypatch.setattr(config, "ENV_PATH", env_file)

        output_path = str(tmp_path / "notes")
        inputs = iter([
            "key",              # API key
            "999",              # User ID
            "n",                # Skip reMarkable
            "2",                # Plain folder
            output_path,        # Folder path
            "",                 # Skip Anthropic
            "",                 # Skip Resend
        ])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("builtins.input", lambda _: next(inputs)), \
             patch("requests.get", return_value=mock_resp):
            from distillate.main import _init_wizard
            _init_wizard()

        text = env_file.read_text()
        assert "OUTPUT_PATH=" in text
        assert Path(output_path).exists()  # Wizard creates the directory

    def test_optional_features_saved(self, tmp_path, monkeypatch):
        from distillate import config

        env_file = tmp_path / ".env"
        monkeypatch.setattr(config, "ENV_PATH", env_file)

        inputs = iter([
            "key",                  # API key
            "999",                  # User ID
            "n",                    # Skip reMarkable
            "3",                    # Skip output
            "sk-ant-test123",       # Anthropic key
            "re_test456",           # Resend key
            "user@example.com",     # Email
        ])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("builtins.input", lambda _: next(inputs)), \
             patch("requests.get", return_value=mock_resp):
            from distillate.main import _init_wizard
            _init_wizard()

        text = env_file.read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-test123" in text
        assert "RESEND_API_KEY=re_test456" in text
        assert "DIGEST_TO=user@example.com" in text
