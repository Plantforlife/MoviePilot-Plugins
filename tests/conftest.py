"""Offline host boundary for this standalone repository.

Tests import the production namespace. Only the event decorator, base class and
logger are substituted; source modules and Jinja2 are real. This does not replace
the separately documented MoviePilot installation/transfer-preview verification.
An upstream MoviePilot test harness can provide its own app package instead.
"""
import importlib.util
import logging
from pathlib import Path
import sys
import types

_created = set()
_before = set()


def pytest_sessionstart(session):
    """Create the minimal host boundary only when no real app package exists."""
    if importlib.util.find_spec('app') is not None:
        return
    _before.update(sys.modules)
    root = Path(__file__).resolve().parents[1]
    paths = {
        'app': [], 'app.sdk': [], 'app.plugins': [str(root / 'plugins.v3')],
        'app.schemas': [],
    }
    for name in [*paths, 'app.sdk.events', 'app.sdk.logging', 'app.schemas.types']:
        module = types.ModuleType(name)
        if name in paths:
            module.__path__ = paths[name]
        sys.modules[name] = module
        _created.add(name)
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            setattr(sys.modules[parent], child, module)

    class EventManager:
        """Leave handlers callable without starting the host event registry."""
        @staticmethod
        def register(event_type):
            return lambda function: function

    class ChainEventType:
        """The two events used by this plugin, with production event names."""
        TransferRenameBuild = 'transfer.rename.build'
        TransferRename = 'transfer.rename'

    sys.modules['app.plugins']._PluginBase = type('_PluginBase', (), {})
    sys.modules['app.sdk.events'].Event = object
    sys.modules['app.sdk.events'].eventmanager = EventManager()
    sys.modules['app.sdk.logging'].logger = logging.getLogger('ffproberename.tests')
    sys.modules['app.schemas.types'].ChainEventType = ChainEventType


def pytest_sessionfinish(session, exitstatus):
    """Remove only modules created by this standalone test session."""
    if not _created:
        return
    for name in list(sys.modules):
        if name in _created or (name.startswith('app.plugins.ffproberename') and name not in _before):
            sys.modules.pop(name, None)
