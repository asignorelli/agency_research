"""Claude Code subscription transport. Never reads .env or calls the paid API SDK."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

from .core import canonical

DEFAULT_MODEL = 'claude-haiku-5-5'
SETTINGS = {'forceLoginMethod': 'claudeai', 'disableAllHooks': True}


def subscription_environment():
    env = os.environ.copy()
    # Print mode otherwise silently prefers API credentials to a subscription.
    for key in (
        'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
        'ANTHROPIC_PROFILE', 'ANTHROPIC_DEFAULT_HAIKU_MODEL',
        'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
        'ANTHROPIC_MODEL', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX',
        'CLAUDE_CODE_USE_FOUNDRY', 'CLAUDE_CODE_USE_AWS', 'CLAUDECODE',
    ):
        env.pop(key, None)
    # OAuth token / normal CLI login stay available; do not read or copy tokens.
    return env


class ClaudeCode:
    def __init__(self, model=DEFAULT_MODEL, effort='medium', timeout=300):
        if not model.startswith('claude-') or any(c.isspace() for c in model):
            raise ValueError('Use an explicit Claude model ID, not a moving alias')
        if effort not in ('low', 'medium', 'high'):
            raise ValueError('Grading effort must be low, medium, or high')
        if not 0 < timeout < float('inf'):
            raise ValueError('Timeout must be positive and finite')
        self.model, self.effort, self.timeout = model, effort, timeout
        self.executable = shutil.which('claude')
        self.version = None

    def flags(self):
        return ['--setting-sources', '', '--settings', canonical(SETTINGS)]

    def check(self, require_login=True):
        if not self.executable:
            raise RuntimeError('Claude Code is missing. Install it, then run claude auth login.')
        with tempfile.TemporaryDirectory(prefix='agency-grader-check-') as cwd:
            opts = dict(cwd=cwd, env=subscription_environment(), text=True,
                        capture_output=True, timeout=30)
            version = subprocess.run([self.executable, '--version'], **opts)
            if version.returncode:
                raise RuntimeError('Could not read the Claude Code version')
            self.version = version.stdout.strip()
            help_result = subprocess.run([self.executable, '--help'], **opts)
            needed = ('--json-schema', '--tools', '--strict-mcp-config',
                      '--setting-sources', '--no-session-persistence', '--effort', '--safe-mode')
            if help_result.returncode or any(flag not in help_result.stdout for flag in needed):
                raise RuntimeError('Update Claude Code; this version lacks required grading flags')
            if not require_login:
                return {'version': self.version, 'login_checked': False}
            auth = subprocess.run([self.executable] + self.flags() + ['auth', 'status'], **opts)
            try:
                state = json.loads(auth.stdout)
            except (ValueError, TypeError):
                state = {}
            logged_in = (auth.returncode == 0 and state.get('loggedIn') is True
                         and state.get('authMethod') in ('claude.ai', 'oauth_token'))
            if not logged_in:
                raise RuntimeError('Claude Code subscription login is required. Run claude auth login, '
                                   'choose your Claude subscription, then repeat this command.')
            return {'version': self.version, 'subscription_login': True,
                    'auth_method': state['authMethod'],
                    'login_freshness': 'Saved login found; expiry can only be confirmed by a model request'}

    def command(self, system, schema):
        return [self.executable] + self.flags() + [
            '--print', '--model', self.model, '--effort', self.effort,
            '--output-format', 'stream-json', '--verbose', '--json-schema', canonical(schema),
            '--system-prompt', system, '--tools', '', '--strict-mcp-config',
            '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands',
            '--no-session-persistence', '--safe-mode', '--no-chrome', '--permission-mode', 'dontAsk',
            '--max-turns', '3',
        ]

    def invoke(self, system, user, schema):
        """Return raw local process output even on failure, before score validation."""
        with tempfile.TemporaryDirectory(prefix='agency-blind-grader-') as cwd:
            try:
                result = subprocess.run(
                    self.command(system, schema), input=user, text=True, capture_output=True,
                    cwd=cwd, env=subscription_environment(), timeout=self.timeout,
                )
                return {'returncode': result.returncode, 'stdout': result.stdout,
                        'stderr': result.stderr, 'timed_out': False,
                        'output_format': 'stream-json'}
            except subprocess.TimeoutExpired as ex:
                def text(value):
                    return value.decode('utf-8', 'replace') if isinstance(value, bytes) else (value or '')
                return {'returncode': None, 'stdout': text(ex.stdout), 'stderr': text(ex.stderr),
                        'timed_out': True, 'output_format': 'stream-json'}


def parse_cli_output(stdout):
    """Read a final JSON envelope or the full JSONL transcript emitted by the CLI.

    modelUsage aggregates foreground and internal/background requests. Only assistant
    message.model identifies the model that produced a grading message in a transcript.
    """
    if not isinstance(stdout, str):
        raise ValueError('Claude Code output must be text')
    try:
        envelope = json.loads(stdout)
    except (ValueError, TypeError):
        events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        if not events or any(not isinstance(event, dict) for event in events):
            raise ValueError('Claude Code returned an invalid event transcript')
        results = [event for event in events if event.get('type') == 'result']
        if len(results) != 1:
            raise ValueError('Claude Code transcript must have one terminal result')
        assistants = [event.get('message') for event in events if event.get('type') == 'assistant']
        return results[0], assistants
    if not isinstance(envelope, dict):
        raise ValueError('Claude Code result must be a JSON object')
    return envelope, []


def decode_response(raw, model):
    if raw.get('timed_out'):
        raise ValueError('Claude Code timed out; subscription usage may already have occurred')
    if raw.get('returncode') != 0:
        # Full process output is preserved privately in the attempt log.
        try:
            error, _ = parse_cli_output(raw.get('stdout') or '{}')
        except (ValueError, TypeError):
            error = {}
        message = str(error.get('result', '')).lower() if isinstance(error, dict) else ''
        if 'oauth' in message or 'authenticate' in message or 'login' in message:
            raise ValueError('Claude Code subscription login expired or failed. Run claude auth login, '
                             'then repeat grading with --retry-failed')
        if 'unrecognized_model' in raw.get('stderr', ''):
            raise ValueError('Claude Code did not recognize the requested model. Update Claude Code '
                             'and confirm model access; no model substitution was made')
        raise ValueError('Claude Code exited with an error; inspect the saved grading attempt')
    envelope, assistants = parse_cli_output(raw['stdout'])
    if not isinstance(envelope, dict) or envelope.get('is_error') or envelope.get('subtype') != 'success':
        raise ValueError('Claude Code did not finish successfully; no grade accepted')
    models = envelope.get('modelUsage')
    if not isinstance(models, dict) or model not in models:
        raise ValueError('Served model is missing or differs from the selected model; no fallback accepted')
    if raw.get('output_format') == 'stream-json' and not assistants:
        raise ValueError('Served model trace is missing from the grading messages; no grade accepted')
    if assistants:
        if any(not isinstance(message, dict) or message.get('model') != model for message in assistants):
            raise ValueError('Served model on a grading message is missing or differs from the selected model; no fallback accepted')
    elif set(models) != {model}:
        # Old final-only replies cannot distinguish grader and background usage. Keep
        # them for the audit trail; do not retroactively guess which model graded.
        raise ValueError('Saved reply has multiple usage models but no grading-message model trace; '
                         'a new traced grading call is required')
    grade = envelope.get('structured_output')
    if not isinstance(grade, dict):
        raise ValueError('Claude Code returned no structured_output grade')
    return grade, envelope
