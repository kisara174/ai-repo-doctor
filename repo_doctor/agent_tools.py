"""Offline, bounded data exchange for repository investigation agents."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .architecture import build_architecture_summary
from .case import source_fingerprint, _static_issues
from .context import build_context
from .diagnosis import MAX_CONTEXT_LINES, validate_context_budget, validate_diagnosis_payload
from .leads import build_review_leads
from .model import RepoIndex


def build_overview(index: RepoIndex) -> dict:
    symbols = sorted(index.symbols.values(), key=lambda item: item.id)
    leads = build_review_leads(index, _static_issues(index))
    return {
        'schema_version': 1,
        'root': str(index.root),
        'scan_mode': index.scan_mode,
        'source_fingerprint': source_fingerprint(index),
        'stats': {
            'python_files': len(index.files), 'symbols': len(symbols),
            'resolved_calls': len(index.call_edges),
            'unresolved_calls': len(index.calls) - len(index.call_edges),
            'parse_errors': len(index.parse_errors), 'ambiguous_symbols': len(index.ambiguous_symbols),
        },
        'architecture': build_architecture_summary(index),
        'review_leads': [{**item, 'subject': item['subject'][:300],
                          'evidence': item['evidence'][:4],
                          'evidence_omitted': item.get('evidence_omitted', 0) + max(0, len(item['evidence']) - 4)}
                         for item in leads[:5]],
        'leads_omitted': max(0, len(leads) - 5),
        'sample_symbols': [{'id': item.id, 'file': item.file, 'kind': item.kind,
                            'start_line': item.start_line} for item in symbols[:10]],
        'symbols_omitted': max(0, len(symbols) - 10),
        'parse_errors': [asdict(item) for item in index.parse_errors[:5]],
        'parse_errors_omitted': max(0, len(index.parse_errors) - 5),
        'next_commands': {
            'symbols': ['repo-doctor', 'symbols', str(index.root), '--query', 'QUERY', '--json'],
            'context': ['repo-doctor', 'context', str(index.root), 'SYMBOL', '--json'],
            'impact': ['repo-doctor', 'impact', str(index.root), 'SYMBOL', '--json'],
        },
        'limitations': ['Static Python analysis only; unresolved calls are coverage limits, not defects.'],
    }


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def write_new_json(path: Path, payload: dict) -> None:
    """Publish a new artifact without replacing repository or user files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def read_json(path: Path) -> object:
    with path.open('rb') as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError('JSON input exceeds 1 MiB')
    return json.loads(data)


def build_snapshot(index: RepoIndex, context: dict, include_symbols: tuple[str, ...]) -> dict:
    request = {'symbol': context['symbol'], 'max_lines': context['max_lines'],
               'include_symbols': list(include_symbols)}
    _validate_snapshot_request(request)
    validate_context_budget(context)
    fingerprint = source_fingerprint(index)
    rebuilt = build_context(index, context['symbol'], context['max_lines'], include_symbols=include_symbols)
    if rebuilt != context or source_fingerprint(index) != fingerprint:
        raise ValueError('source changed during context collection')
    body = {
        'schema_version': 1, 'root': str(index.root), 'source_fingerprint': fingerprint,
        'request': request,
        'context': context,
    }
    return {**body, 'snapshot_sha256': _digest(body)}


def _validate_snapshot_request(request: dict) -> None:
    budget, includes = request['max_lines'], request['include_symbols']
    if (isinstance(budget, bool) or not isinstance(budget, int)
            or not 1 <= budget <= MAX_CONTEXT_LINES or not isinstance(includes, list)
            or len(includes) > MAX_CONTEXT_LINES or not all(isinstance(item, str) for item in includes)
            or not isinstance(request['symbol'], str)):
        raise ValueError('invalid context snapshot request; budget must be 1..120 lines')


def validate_snapshot(index: RepoIndex, snapshot: object) -> dict:
    try:
        if not isinstance(snapshot, dict) or snapshot.get('schema_version') != 1:
            raise ValueError('invalid context snapshot schema')
        body = {key: value for key, value in snapshot.items() if key != 'snapshot_sha256'}
        if snapshot.get('snapshot_sha256') != _digest(body):
            raise ValueError('context snapshot hash mismatch')
        if snapshot['root'] != str(index.root):
            raise ValueError('context snapshot repository mismatch')
        fingerprint = source_fingerprint(index)
        if snapshot['source_fingerprint'] != fingerprint:
            raise ValueError('source changed since context snapshot; collect context again')
        request = snapshot['request']
        _validate_snapshot_request(request)
        budget = request['max_lines']
        includes = request['include_symbols']
        rebuilt = build_context(index, request['symbol'], budget, include_symbols=tuple(includes))
        if snapshot['context'] != rebuilt or source_fingerprint(index) != fingerprint:
            raise ValueError('context snapshot does not match current source')
        return rebuilt
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('invalid context snapshot structure') from exc


def validate_agent_findings(index: RepoIndex, payload: object, context: dict) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get('findings'), list):
        raise ValueError('input must contain a findings list')
    return validate_diagnosis_payload(index, payload, context)
