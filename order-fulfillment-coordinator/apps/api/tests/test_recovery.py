from pathlib import Path
import os
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("mode", ["check", "missing_image", "replacement_without_review", "outside_root"])
def test_recovery_preflight_never_changes_running_services(tmp_path, mode):
    bash = shutil.which("bash") or ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else None)
    if not bash:
        pytest.skip("Bash unavailable")
    root = Path(__file__).resolve().parents[3]
    state = tmp_path / "state"
    release_root = tmp_path / "releases"
    previous = release_root / "prior/order-fulfillment-coordinator"
    previous.mkdir(parents=True)
    state.mkdir()
    (state / "previous-release").write_text(previous.as_posix())
    (previous / ".env").write_text("DOMAIN=example.test\n")
    (previous / "docker-compose.prod.yml").write_text("services: {}\n")
    (previous / "release.env").write_text("TAG=" + "a" * 40 + "\nIMAGE_OWNER=fixture\n" +
        "API_IMAGE_REF=ghcr.io/fixture/fulfillment-api@sha256:" + "b" * 64 + "\n" +
        "FRONTEND_IMAGE_REF=ghcr.io/fixture/fulfillment-ui@sha256:" + "c" * 64 + "\n")
    harness = tmp_path / "harness.sh"
    harness.write_text('''
docker() {
 printf '%s\\n' "$*" >> "$CALLS"
 if [[ "$*" == *"image inspect"* && "$TEST_FAILURE" == missing_image ]]; then return 1; fi
 return 0
}
flock() { return 0; }
export -f docker flock
bash "$@"
''')
    env = {**os.environ, "DEPLOY_STATE_DIR": state.as_posix(),
           "DEPLOY_RELEASE_ROOT": release_root.as_posix(), "TEST_FAILURE": mode,
           "CALLS": (tmp_path / "calls").as_posix()}
    if mode == "outside_root":
        (state / "previous-release").write_text(tmp_path.as_posix())
    option = "--replace-services" if mode == "replacement_without_review" else "--check"
    result = subprocess.run([bash, str(harness), str(root / "infra/scripts/recover-release.sh"), option],
                            env=env, capture_output=True, text=True, timeout=20)
    assert (result.returncode == 0) == (mode == "check"), result.stdout + result.stderr
    calls = (tmp_path / "calls").read_text() if (tmp_path / "calls").exists() else ""
    assert "up -d" not in calls and " pull" not in calls and "alembic" not in calls
    assert not (state / "current-release").exists()
