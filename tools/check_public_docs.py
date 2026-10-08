"""Check maintained user instructions locally, never fetching external links."""

import argparse
import ast
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

PUBLIC_DOCS = ('README.md', 'docs/INSTALL.md', 'docs/CODEX_AND_MAP.md', 'docs/JS_TS_SUPPORT.md',
               'docs/CLI_CONTRACT.md', 'docs/RESOURCE_LIMITS.md', 'docs/SUPPORT_MATRIX.md')
_VERSION = r'[0-9]+(?:\.[0-9]+)+(?:[a-zA-Z0-9.]+)?'


def check_document(root: Path, path: Path, source_version: str) -> list[str]:
    text = path.read_text(encoding='utf-8')
    install_marker = re.search(r'<!--\s*repo-doctor-install-versions:\s*([^>]+?)\s*-->', text)
    versions = {item.strip() for item in install_marker[1].split(',')} if install_marker else {source_version}
    errors, prose = [], []
    display = str(path.relative_to(root))
    development = re.search(r'<!--\s*repo-doctor-development-version:\s*([^>]+?)\s*-->', text)
    if development and development[1].strip() != source_version:
        errors.append(f'{display}: development version differs from source {source_version}')
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if fence is None:
            prose.append((number, line))
            continue
        if re.search(r'/(?:Users|home)/[^\s/]+/', line):
            errors.append(f'{display}:{number}: maintainer home path in runnable example')
        literals = []
        for pattern in (rf'ai_repo_doctor-({_VERSION})-py3-none-any\.whl',
                        rf'/releases/download/v({_VERSION})(?:/|$)',
                        rf'\bRD_VERSION=[\'"]?({_VERSION})(?:[\'"\s]|$)',
                        rf'ai-repo-doctor(?:\[[^\]]+\])?==({_VERSION})'):
            literals.extend(re.findall(pattern, line))
        if any(value not in versions for value in literals):
            errors.append(f'{display}:{number}: install version must be one of {sorted(versions)}')
    for number, line in prose:
        # Handle inline links, angle-bracket destinations and reference definitions.
        targets = re.findall(r'!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)', line)
        reference = re.match(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)', line)
        if reference:
            targets.append(reference[1])
        for target in targets:
            target = target.strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            relative = Path(unquote(parsed.path))
            destination = path.parent / relative
            if relative.is_absolute() or not destination.exists():
                errors.append(f'{display}:{number}: missing or nonportable local link: {target}')
    return errors


def check_public_docs(root: Path) -> list[str]:
    root = root.resolve()
    version = None
    module = ast.parse((root / 'repo_doctor/_version.py').read_text())
    for item in module.body:
        if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == '__version__' for target in item.targets):
            version = ast.literal_eval(item.value)
    if not isinstance(version, str):
        raise ValueError('Source __version__ is missing or not a literal string')
    errors = []
    for relative in PUBLIC_DOCS:
        path = root / relative
        if not path.is_file():
            errors.append(f'{relative}: required public document is missing')
        else:
            errors.extend(check_document(root, path, version))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        errors = check_public_docs(args.root)
    except (OSError, ValueError, SyntaxError) as exc:
        parser.exit(2, f'error: {exc}\n')
    if errors:
        parser.exit(1, '\n'.join(errors) + '\n')
    print(f'Public docs: {len(PUBLIC_DOCS)} documents checked; local links/examples/versions passed')


if __name__ == '__main__':
    main()
