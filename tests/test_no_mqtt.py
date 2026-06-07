from pathlib import Path
import re


TARGET_DIRS = ["custom_components", "src"]
PROHIBITED_PATTERNS = [
    re.compile(r"\bimport\s+paho\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+paho\b", re.IGNORECASE),
    re.compile(r"\bpaho-mqtt\b", re.IGNORECASE),
    re.compile(r"\bhomeassistant\.components\.mqtt\b", re.IGNORECASE),
    re.compile(r"\bPlatform\.MQTT\b", re.IGNORECASE),
]


def test_no_mqtt_dependencies_or_imports() -> None:
    for target in TARGET_DIRS:
        root = Path(target)
        for path in root.rglob("*"):
            if path.is_dir() or path.suffix not in {".py", ".json", ".toml"}:
                continue
            content = path.read_text(encoding="utf-8")
            for pattern in PROHIBITED_PATTERNS:
                assert not pattern.search(content), (
                    f"Prohibited MQTT dependency/import found in {path}: {pattern.pattern}"
                )
