"""Keep the local proxy and its clients on the same private authentication key."""
from pathlib import Path
import os
import secrets
import sys
import tempfile


def configure(path: Path):
    original = path.read_text() if path.exists() else ''
    values = {}
    for line in original.splitlines():
        key, separator, value = line.partition('=')
        if separator and key in {'LITELLM_MASTER_KEY', 'LLM_SERVER_API_KEY'}:
            values[key] = value.strip().strip('\"\'')
    key = values.get('LITELLM_MASTER_KEY') or values.get('LLM_SERVER_API_KEY') or 'sk-' + secrets.token_hex(32)
    lines = [line for line in original.splitlines() if line.partition('=')[0] not in {'LITELLM_MASTER_KEY', 'LLM_SERVER_API_KEY'}]
    content = '\n'.join(lines + [f'LITELLM_MASTER_KEY={key}', f'LLM_SERVER_API_KEY={key}']) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if content != original:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as temp:
            temp.write(content)
        os.replace(temp.name, path)
    path.chmod(0o600)


if __name__ == '__main__':
    configure(Path(sys.argv[1]))
