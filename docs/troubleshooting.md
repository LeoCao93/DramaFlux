# Troubleshooting

## ADB 不可用

不要使用系统 PATH 中不存在的 `adb`，直接调用 MuMu 自带版本：

```powershell
& "D:\MuMu Player 12\shell\adb.exe" connect 127.0.0.1:16384
& "D:\MuMu Player 12\shell\adb.exe" devices -l
```

## root 不可用

```powershell
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell "su -c id"
```

预期包含 `uid=0(root)`。root 用于启动和检查 `frida-server`，普通 ADB 权限无法
附加其他 App 进程。

## Frida 版本不一致

```powershell
uv run python -c "import frida; print(frida.__version__)"
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell `
  "su -c '/data/local/tmp/frida-server --version'"
```

两个版本必须完全一致。

## 红果进程变化

```powershell
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell `
  "pidof com.phoenix.read"
```

watchdog 会尝试重新附加；持续失败时调用 `/v1/admin/reconnect` 或重启 Signer。

## 会话过期

保持 Signer 运行，在红果内触发自然网络请求，然后重新执行：

```powershell
.\services\api-server\scripts\capture_session.ps1
```

## 离线验证

```powershell
$env:UV_CACHE_DIR="D:\Codex\hongguo-video\.uv-cache"
uv run pytest -q
uv run ruff check .
```

真实测试只在 `HONGGUO_RUN_LIVE_TESTS=1` 时运行。
