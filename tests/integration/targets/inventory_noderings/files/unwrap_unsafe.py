"""Read ansible-inventory JSON and drop the {"__ansible_unsafe": ...} wrappers."""
import json
import sys


def unwrap(value):
    if isinstance(value, dict):
        if list(value) == ["__ansible_unsafe"]:
            return unwrap(value["__ansible_unsafe"])
        return {k: unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    return value


print(json.dumps(unwrap(json.load(sys.stdin))))
