"""Validate marketplace metadata, source files and generated default examples."""
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PID = 'FfprobeRename'


def check():
    """Fail before publication if an installable release would be inconsistent."""
    index = json.loads((ROOT / 'package.v3.json').read_text(encoding='utf-8'))
    assert set(index) == {PID}, 'Unexpected marketplace entries'
    data = index[PID]
    plugin = ROOT / 'plugins.v3' / PID.lower()
    tree = ast.parse((plugin / '__init__.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == PID)
    fields = {n.targets[0].id: ast.literal_eval(n.value) for n in cls.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
    for source, key in [('plugin_name', 'name'), ('plugin_desc', 'description'), ('plugin_version', 'version'), ('plugin_author', 'author'), ('plugin_icon', 'icon'), ('auth_level', 'level')]:
        assert fields[source] == data[key], f'Metadata mismatch: {key}'
    assert re.fullmatch(r'\d+\.\d+\.\d+', data['version']), 'Invalid semantic version'
    versions = list(data['history'])
    assert versions[0] == 'v' + data['version'], 'Current history must be first'
    assert versions == sorted(versions, key=lambda x: tuple(map(int, x.removeprefix('v').split('.'))), reverse=True)
    assert data['release'] is True
    assert data['system_version'] == '>=3.1.4'
    assert (ROOT / 'icons' / 'ffproberename.png').is_file()
    for module, mapping in {
        'naming.py': {'DEFAULT_RULES': 'rules.ini', 'DEFAULT_PREFER_ENGLISH': 'prefer-english.txt'},
        'probe.py': {'DEFAULT_GROUP_MAP': 'group-map.txt', 'DEFAULT_EDITION_MAP': 'edition-map.txt', 'DEFAULT_KNOWN_GROUPS': 'known-groups.txt', 'DEFAULT_PLATFORMS': 'platforms.txt'},
    }.items():
        body = ast.parse((plugin / module).read_text(encoding='utf-8')).body
        for node in body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in mapping:
                expected = ast.literal_eval(node.value)
                actual = (ROOT / 'examples' / mapping[node.targets[0].id]).read_text(encoding='utf-8')
                assert actual == expected, f'Outdated example: {node.targets[0].id}'
    for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md']:
        assert (plugin / name).is_file(), f'Missing release document: {name}'
    print(f'{PID} {data["version"]}: marketplace, history and examples valid')


if __name__ == '__main__':
    check()
