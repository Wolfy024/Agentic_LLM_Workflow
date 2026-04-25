# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for LLM Orchestrator
Build with: pyinstaller llm-orchestrator.spec
"""

import sys
from pathlib import Path

# Add backend to path so imports resolve
spec_dir = Path(sys.argv[0]).resolve().parent
backend_dir = spec_dir.parent  # landing-page/parent = backend/
sys.path.insert(0, str(backend_dir))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=[
        ('../config.json', '.'),
        ('../.env', '.'),
    ],
    hiddenimports=[
        # Agent
        'agent.executor',
        'agent.runner',
        'agent.state',
        'agent.tokens',
        'agent.watch.queue',
        'agent.watch.service',
        'agent.watch.state',
        'agent.watch.utils',
        # Core
        'core.bootstrap',
        'core.cache',
        'core.config',
        'core.permissions_checks',
        'core.permissions_prompts',
        'core.prefs',
        'core.repl_utils',
        'core.runtime_config',
        # LLM
        'llm.client',
        'llm.errors',
        'llm.stream',
        'llm.vision',
        # REPL
        'repl.loop',
        'repl.slash',
        'repl.commands.config',
        'repl.commands.info',
        'repl.commands.inject',
        'repl.commands.session',
        'repl.commands.watch',
        # Tools
        'tools.registry',
        'tools.fs.edit',
        'tools.fs.external',
        'tools.fs.image',
        'tools.fs.read',
        'tools.fs.search',
        'tools.fs.write',
        'tools.git.core',
        'tools.git.diff',
        'tools.git.github',
        'tools.git.info',
        'tools.git.ops',
        'tools.git.remote_sync',
        'tools.image_gen',
        'tools.system',
        'tools.web.fetch',
        'tools.web.serper',
        # UI
        'ui.banner',
        'ui.components',
        'ui.console',
        'ui.context_logs',
        'ui.dimming',
        'ui.help',
        'ui.markdown',
        'ui.palette',
        'ui.repl_bindings',
        'ui.slash_complete',
        'ui.streaming',
        'ui.tool_logs',
        # Third-party (inside try/except, not auto-detected)
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'setuptools',
        'tkinter',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='llm-orchestrator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
