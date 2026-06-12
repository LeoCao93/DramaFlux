from pathlib import Path


SERVICE_ROOT = Path(__file__).parents[2]


def test_env_example_documents_bootstrap_configuration() -> None:
    source = (SERVICE_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "HONGGUO_SIGNER_FRIDA_SERVER_PATH=" in source
    assert "HONGGUO_SIGNER_FRIDA_REMOTE_PATH=" in source
    assert "HONGGUO_SIGNER_FRIDA_PORT=27042" in source
    assert "HONGGUO_SIGNER_WATCHDOG_INTERVAL=15" in source
    assert "HONGGUO_SIGNER_SERVICE_TOKEN=" in source


def test_scripts_resolve_workspace_and_use_uv_project() -> None:
    for name in ("check_environment.ps1", "start.ps1"):
        source = (SERVICE_ROOT / "scripts" / name).read_text(encoding="utf-8")

        assert "$PSScriptRoot" in source
        assert "UV_CACHE_DIR" in source
        assert "--project $ServiceRoot" in source
        assert "Invoke-WebRequest" not in source
        assert "curl " not in source.lower()


def test_start_script_leaves_application_assembly_for_task_10() -> None:
    source = (SERVICE_ROOT / "scripts" / "start.ps1").read_text(
        encoding="utf-8"
    )

    assert "hongguo_signer.bootstrap_app:app" in source
