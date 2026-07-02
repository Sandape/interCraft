"""Unit tests for REQ-038 structured coverage checker."""
from __future__ import annotations

import subprocess
import sys


def test_structured_coverage_rejects_unsigned_node(tmp_path_factory) -> None:
    backend_root = tmp_path_factory.mktemp("backend")
    agents_root = backend_root / "app" / "agents"
    unsigned_dir = agents_root / "interview" / "nodes"
    unsigned_dir.mkdir(parents=True)
    script_dir = backend_root / "scripts"
    script_dir.mkdir()

    source_script = __import__("pathlib").Path(__file__).resolve().parents[2] / "scripts" / "check_structured_coverage.py"
    check_script = script_dir / "check_structured_coverage.py"
    check_script.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")

    (unsigned_dir / "test_unsigned.py").write_text(
        "async def test_unsigned_node(client):\n"
        "    result = await client.invoke(messages=[], node_name='unsigned')\n"
        "    return result\n",
        encoding="utf-8",
    )

    package_dir = agents_root / "structured_output"
    package_dir.mkdir(parents=True)
    for init_dir in [backend_root / "app", agents_root, package_dir]:
        (init_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "registry.py").write_text(
        "STRUCTURED_NODES = ['interview.intake', 'interview.score', 'error_coach.evaluate']\n"
        "NODE_SCHEMAS = {\n"
        "    'interview.intake': (object, object),\n"
        "    'interview.score': (object, object),\n"
        "    'error_coach.evaluate': (object, object),\n"
        "}\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(check_script)],
        cwd=backend_root,
        text=True,
        capture_output=True,
        check=False,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode == 1
    assert "test_unsigned.py" in combined
    assert "not registered" in combined or "missing" in combined
