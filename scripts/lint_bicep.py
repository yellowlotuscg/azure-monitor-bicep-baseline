#!/usr/bin/env python3
"""Dependency-free structural checks for this small lab, NOT a Bicep compiler."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(source, parameters):
    # Preserve positions, but hide comments and strings from delimiter checks.
    # This intentionally supports only the single-line strings used by this lab.
    token = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'")
    clean = token.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), source)
    assert "'" not in clean, 'Unterminated or unsupported string'
    stack, ends = [], {}
    pairs = {')': '(', ']': '[', '}': '{'}
    for i, char in enumerate(clean):
        if char in '([{':
            stack.append((char, i))
        elif char in ')]}':
            assert stack and stack[-1][0] == pairs[char], 'Mismatched delimiter at {}'.format(i)
            _, start = stack.pop()
            ends[start] = i
    assert not stack, 'Unclosed delimiter'
    assert re.search(r"^targetScope = 'resourceGroup'$", source, re.M), 'Expected resourceGroup scope'
    declarations = re.findall(r'^param\s+(\w+)\s+(string|int|bool|array|object)\b([^\n]*)', source, re.M)
    declared = {name for name, _, _ in declarations}
    assert len(declared) == len(declarations), 'Duplicate parameter'
    supplied = set(parameters['parameters'])
    assert supplied <= declared, 'Undeclared parameter in parameter file'
    required = {name for name, _, default in declarations if '=' not in default}
    assert required <= supplied, 'Missing required parameter value'
    symbols = set(re.findall(r'^(?:param|var|resource|output)\s+(\w+)', source, re.M))
    # Check bare identifiers and simple interpolations against declarations.
    allowed = symbols | {'targetScope', 'param', 'var', 'resource', 'output',
                         'string', 'int', 'bool', 'array', 'object', 'true', 'false',
                         'description', 'minLength', 'maxLength', 'secure',
                         'resourceGroup', 'uniqueString'}
    for match in re.finditer(r'\b[A-Za-z_][A-Za-z0-9_]*\b', clean):
        before, after = clean[:match.start()].rstrip(), clean[match.end():].lstrip()
        if before.endswith('.') or after.startswith(':'):
            continue
        assert match[0] in allowed, 'Unknown identifier: ' + match[0]
    for expression in re.findall(r'\$\{([^}]+)\}', source):
        assert re.fullmatch(r'\w+(?:\.\w+)*', expression), 'Unsupported interpolation'
        assert expression.split('.')[0] in symbols, 'Unknown interpolation: ' + expression
    resources = re.findall(r"^resource\s+(\w+)\s+'([^']+)'\s*=\s*\{", source, re.M)
    assert len(resources) == 6, 'Expected six resources'
    assert len({name for name, _ in resources}) == 6, 'Duplicate resource symbol'
    for match in re.finditer(r"^resource\s+(\w+)\s+'([^']+)'\s*=\s*\{", source, re.M):
        name, type_version = match[1], match[2]
        assert re.fullmatch(r'Microsoft\.[A-Za-z]+/\w+@\d{4}-\d{2}-\d{2}', type_version), 'Missing type/API version'
        body = clean[match.end():ends[match.end() - 1]]
        assert re.search(r'^  name:', body, re.M), 'Missing resource name: ' + name
        assert re.search(r'^  location:', body, re.M), 'Missing resource location: ' + name
    assert sum('/metricAlerts@' in kind for _, kind in resources) == 2, 'Expected two metric alerts'
    assert source.count('actionGroupId: actionGroup.id') == 2, 'Both alerts must notify'
    assert 'WorkspaceResourceId: workspace.id' in source, 'Workspace link missing'
    return len(resources), len(declared)


def main():
    source = (ROOT / 'main.bicep').read_text()
    parameters = json.loads((ROOT / 'main.parameters.json').read_text())
    resources, params = check(source, parameters)
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(part in {'.git', '__pycache__'} for part in path.relative_to(ROOT).parts):
            continue
        assert chr(0x2014).encode() not in path.read_bytes(), 'Forbidden punctuation: ' + str(path)
    if '--self-test' in sys.argv:
        mutations = [source + '\n}', source.replace('emailAddress: alertEmail', 'emailAddress: missingEmail'),
                     source.replace('WorkspaceResourceId: workspace.id', 'WorkspaceResourceId: absent.id'),
                     source.replace('@2023-09-01', '@invalid'), source.replace('  name: webTestName', '  missing: webTestName')]
        for mutation in mutations:
            try:
                check(mutation, parameters)
            except AssertionError:
                continue
            raise AssertionError('Negative fixture was not rejected')
        print('PASS: five negative fixtures rejected')
    print('PASS: balanced delimiters; {} typed/versioned/named resources; {} declared parameters; symbol checks; two alert actions; no forbidden punctuation'.format(resources, params))
    print('LIMIT: structural checks only, no compilation, Azure validation or deployment performed')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, ValueError) as exc:
        sys.exit('FAIL: ' + str(exc))
