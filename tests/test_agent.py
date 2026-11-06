"""The agent plugin, run with a fake `ceph` command in place of the real one.

The script honours CEPH_CMD, so the fake replays the Reef output in
tests/data/ and the test reads back exactly what the Checkmk agent would
send, then splits it into sections the way Checkmk does.
"""

import importlib.util
import json
import os
import pathlib
import re
import stat
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENT = ROOT / "local/share/check_mk/agents/plugins/oposs_ceph"
CHECK = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_ceph/agent_based/oposs_ceph.py"
DATA = pathlib.Path(__file__).resolve().parent / "data"

FAKE_CEPH = """#!/bin/sh
echo "$*" >> "{log}"
case "$*" in
  "status -f json") cat "{data}/status_ok.json" ;;
  "osd perf -f json") cat "{data}/osd_perf.json" ;;
  "df detail -f json") cat "{data}/df_detail.json" ;;
  *) echo "unexpected: $*" >&2; exit 22 ;;
esac
"""

FAILING_CEPH = """#!/bin/sh
echo "[errno 13] RADOS permission denied (error connecting to the cluster)" >&2
exit 13
"""


@pytest.fixture(scope="module")
def check():
    name = "test_oposs_ceph_check_agent"
    spec = importlib.util.spec_from_file_location(name, CHECK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(name, None)


def _fake(tmp_path, body):
    path = tmp_path / "ceph"
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _run(ceph):
    env = dict(os.environ, CEPH_CMD=str(ceph))
    return subprocess.run(["bash", str(AGENT)], check=False, env=env, capture_output=True, text=True, timeout=30)


def _sections(output):
    """Split agent output into {name: string table}, as Checkmk does for sep(0)."""
    sections = {}
    current = None
    for line in output.splitlines():
        header = re.fullmatch(r"<<<(\w+)(?::sep\(0\))?>>>", line)
        if header:
            current = sections.setdefault(header.group(1), [])
        elif current is not None:
            current.append([line])
    return sections


def test_agent_is_executable():
    assert os.access(AGENT, os.X_OK)


def test_agent_syntax():
    subprocess.run(["bash", "-n", str(AGENT)], check=True)


def test_agent_runs_the_three_ceph_commands(tmp_path):
    log = tmp_path / "calls"
    result = _run(_fake(tmp_path, FAKE_CEPH.format(log=log, data=DATA)))
    assert result.returncode == 0
    assert log.read_text().splitlines() == ["status -f json", "osd perf -f json", "df detail -f json"]


def test_agent_output_parses_into_all_sections(tmp_path, check):
    result = _run(_fake(tmp_path, FAKE_CEPH.format(log=tmp_path / "calls", data=DATA)))
    sections = _sections(result.stdout)
    assert list(sections) == ["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"]
    status = check._parse_json_section(sections["oposs_ceph_status"])
    perf = check._parse_json_section(sections["oposs_ceph_osd_perf"])
    df = check._parse_json_section(sections["oposs_ceph_df"])
    assert status["health"]["status"] == "HEALTH_OK"
    assert len(perf["osdstats"]["osd_perf_infos"]) == 12
    assert [p["name"] for p in df["pools"]] == [".mgr", "rbd", "cephfs.data"]


def test_agent_with_failing_ceph_sends_empty_sections(tmp_path, check):
    result = _run(_fake(tmp_path, FAILING_CEPH))
    # stderr of ceph is dropped, so nothing but the headers reaches Checkmk
    assert result.stdout.splitlines() == [
        "<<<oposs_ceph_status:sep(0)>>>",
        "<<<oposs_ceph_osd_perf:sep(0)>>>",
        "<<<oposs_ceph_df:sep(0)>>>",
    ]
    for table in _sections(result.stdout).values():
        assert check._parse_json_section(table) == {}


def test_agent_without_ceph_installed(tmp_path):
    result = _run(tmp_path / "no-such-ceph")
    assert result.stdout.count("<<<") == 3
    assert result.stdout.count("\n") == 3


def test_agent_carries_the_released_version():
    # The publish check fails on main when a version file disagrees with
    # the newest released CHANGES.md heading.
    assert re.search(rf'^PLUGIN_VERSION="{re.escape(_released_version())}"$',
                     AGENT.read_text(), flags=re.MULTILINE)


def test_agent_is_executable_in_git():
    # The Checkmk agent skips plugins without the executable bit; the MKP
    # build takes the mode from git.
    out = subprocess.run(["git", "ls-files", "-s", AGENT.name], cwd=AGENT.parent,
                         capture_output=True, text=True, check=True).stdout
    assert out.split()[0] == "100755"


def _released_version():
    """The newest released heading of CHANGES.md, the version the publish
    check expects in every version_files target between releases."""
    return re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGES.md").read_text(),
                     flags=re.MULTILINE).group(1)


def test_release_writes_version_into_agent(tmp_path):
    """Apply the version_files entry of .github/repo-infra.json to a copy of
    the agent, as Create release PR does (a multiline regex, first match)"""
    config = json.loads((ROOT / ".github/repo-infra.json").read_text())
    (spec,) = [f for f in config["version_files"] if pathlib.Path(f["path"]).name == AGENT.name]
    assert ROOT / spec["path"] == AGENT
    stamped = re.sub(spec["pattern"], spec["replacement"].replace("$VERSION", "9.8.7"),
                     AGENT.read_text(), count=1, flags=re.MULTILINE)
    assert re.search(spec["verify"].replace("$VERSION", re.escape("9.8.7")), stamped, flags=re.MULTILINE)
    copy = tmp_path / "oposs_ceph"
    copy.write_text(stamped)
    # Read the variable the way bash does, without running the ceph commands
    shown = subprocess.run(
        ["bash", "-c", 'eval "$(grep -m1 "^PLUGIN_VERSION=" "$1")"; echo "$PLUGIN_VERSION"', "_", str(copy)],
        check=True, capture_output=True, text=True)
    assert shown.stdout == "9.8.7\n"
