"""Offline regression checks for release validation and deployment failure handling."""
from __future__ import annotations

import base64
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
INFRA = ROOT / "order-fulfillment-coordinator" / "infra"
encode_settings = runpy.run_path(str(ROOT / ".github/scripts/prepare_deploy_env.py"))["encode_settings"]
is_ready = runpy.run_path(str(INFRA / "scripts/check_readiness.py"))["is_ready"]


def settings():
    return {f"CFG_{key}": "test-value" for key in (
        "POSTGRES_PASSWORD", "JWT_SECRET", "WEBHOOK_SECRET", "INTEGRATION_SECRET_KEY",
        "OPENAI_API_KEY", "DOMAIN", "FRONTEND_URL",
    )}


def test_dotenv_preserves_shell_metacharacters_without_evaluation():
    env = settings()
    env["CFG_JWT_SECRET"] = 'literal$HOME# space`id`$(id)'
    encoded = base64.b64decode(encode_settings(env)).decode()
    assert "JWT_SECRET='literal$HOME# space`id`$(id)'" in encoded
    assert "PATH=" not in encoded


@pytest.mark.parametrize("unsafe", ["one\ntwo", "one\rtwo", "a'b", "a\\b", "a\0b"])
def test_dotenv_rejects_multiline_or_ambiguous_values(unsafe):
    env = settings()
    env["CFG_JWT_SECRET"] = unsafe
    with pytest.raises(ValueError, match="JWT_SECRET"):
        encode_settings(env)


def test_missing_required_settings_names_only():
    with pytest.raises(ValueError, match="Missing deployment settings"):
        encode_settings({"CFG_OPENAI_API_KEY": "never-print-this"})


def test_dotenv_refuses_passwords_that_break_the_database_url():
    env = settings()
    env["CFG_POSTGRES_PASSWORD"] = "unsafe@password"
    with pytest.raises(ValueError, match="URL-safe"):
        encode_settings(env)


@pytest.mark.parametrize("payload", [
    {}, {"status": "degraded"}, {"status": "ok"}, "status ok", [],
    {"status": "ok", "backends": {"postgres": True, "celery": False, "qdrant": True}},
    {"status": "ok", "backends": {"postgres": "true", "celery": True, "qdrant": True}},
])
def test_readiness_rejects_partial_or_malformed_health(payload):
    assert not is_ready(payload)


def test_readiness_requires_all_production_backends():
    assert is_ready({"status": "ok", "backends": dict.fromkeys(("postgres", "celery", "qdrant"), True)})


@pytest.mark.parametrize("failure", ["none", "existing", "pull", "migration", "readiness", "collision", "lock", "caddy", "tls", "registry"])
def test_deploy_command_flow_and_failure_propagation(tmp_path, failure):
    bash = shutil.which("bash")
    if not bash and os.name == "nt":
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(candidate) if candidate.exists() else None
    if not bash:
        pytest.skip("Bash unavailable")
    release = tmp_path / "release"
    scripts = release / "infra/scripts"
    scripts.mkdir(parents=True)
    shutil.copy(INFRA / "scripts/deploy.sh", scripts)
    shutil.copy(INFRA / "scripts/check_readiness.py", scripts)
    (release / ".env").write_text("DOMAIN=example.test\n")
    (release / "docker-compose.prod.yml").write_text("services: {}\n")
    harness = tmp_path / "harness.sh"
    harness.write_text(r'''
set -e
docker() {
    printf '%s\n' "$*" >> "$CALLS"
    case " $* " in
      *" container inspect "*) [[ "$FAILURE" == collision || "$FAILURE" == existing ]]; return ;;
      *" inspect -f "*)
        if [[ "$FAILURE" == existing ]]; then
          if [[ "$*" == *com.docker.compose.project* ]]; then echo order-fulfillment-coordinator;
          else name="${!#}"; name="${name#order-fulfillment-coordinator-}"; echo "${name%-1}"; fi
        else echo unrelated; fi
        return ;;
      *" login "*) cat >/dev/null; [[ "$FAILURE" != registry ]]; return ;;
      *" image inspect "*) image="${!#}"; printf '%s@sha256:%064d\n' "${image%:*}" 0; return ;;
      *" pull "*) [[ "$FAILURE" != pull ]]; return ;;
      *" caddy validate "*) [[ "$FAILURE" != caddy ]]; return ;;
      *" alembic upgrade head "*) [[ "$FAILURE" != migration ]]; return ;;
      *" config --format json "*) echo '{"services":{"caddy":{"environment":{"DOMAIN":"example.test"}}}}'; return ;;
      *" exec -T api python "*)
        [[ "$FAILURE" != readiness ]] || return 1
        while [[ "$1" != python ]]; do shift; done
        shift
        if [[ "$1" == - ]]; then cat >/dev/null; return 0; fi
        "$TEST_PY" "$@"
        return ;;
    esac
    return 0
}
curl() { [[ "$FAILURE" != tls ]] || return 22; echo '{"status":"ok","backends":{"postgres":true,"celery":true,"qdrant":true}}'; }
sleep() { :; }
flock() { [[ "$FAILURE" != lock ]]; }
export -f docker curl sleep flock
bash "$1"
''', encoding="utf-8")
    env = {**os.environ, "TAG": "a" * 40, "IMAGE_OWNER": "Example", "FAILURE": failure,
           "DEPLOY_STATE_DIR": (tmp_path / "state").as_posix(),
           "CALLS": (tmp_path / "calls").as_posix(), "TEST_PY": Path(sys.executable).as_posix()}
    for name in ("CONFIG_B64", "REGISTRY_TOKEN", "DOCKER_HOST", "DOCKER_CONTEXT"):
        env.pop(name, None)
    if failure == "registry":
        env.update(REGISTRY_TOKEN="local-fixture-token", REGISTRY_USER="fixture")
    result = subprocess.run([bash, str(harness), str(scripts / "deploy.sh")],
                            env=env, capture_output=True, text=True, timeout=30)
    success = failure in ("none", "existing")
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    current = tmp_path / "state/current-release"
    assert current.exists() == success
    calls = (tmp_path / "calls").read_text() if (tmp_path / "calls").exists() else ""
    assert " down " not in calls and " rm " not in calls
    assert "prune" not in calls and "--build" not in calls
    if failure in ("pull", "collision", "lock"):
        assert "up -d" not in calls
    if failure == "pull":
        assert " pull" in calls
    if failure == "migration":
        assert "alembic upgrade head" in calls
    if failure == "readiness":
        assert "exec -T api python" in calls
