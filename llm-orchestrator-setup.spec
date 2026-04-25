# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['entrypoint.py'],
    pathex=['.', 'backend'],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=[
        # installer
        'installer',
        # tools
        'tools', 'tools.registry', 'tools.system', 'tools.image_gen',
        'tools._subprocess_utf8',
        # tools.fs
        'tools.fs', 'tools.fs.read', 'tools.fs.write', 'tools.fs.edit',
        'tools.fs.search', 'tools.fs.external', 'tools.fs.image',
        # tools.git
        'tools.git', 'tools.git.core', 'tools.git.diff', 'tools.git.info',
        'tools.git.ops', 'tools.git.remote_sync', 'tools.git.github',
        # tools.web
        'tools.web', 'tools.web.serper', 'tools.web.fetch',
        # core
        'core', 'core.config', 'core.bootstrap', 'core.runtime_config',
        'core.permissions_checks', 'core.permissions_prompts', 'core.prefs',
        'core.cache', 'core.repl_utils',
        # agent
        'agent', 'agent.runner', 'agent.executor', 'agent.state', 'agent.tokens',
        'agent.watch', 'agent.watch.queue', 'agent.watch.service',
        'agent.watch.state', 'agent.watch.utils',
        # llm
        'llm', 'llm.client', 'llm.errors', 'llm.stream', 'llm.vision',
        # repl
        'repl', 'repl.loop', 'repl.slash',
        'repl.commands', 'repl.commands.config', 'repl.commands.info',
        'repl.commands.inject', 'repl.commands.session', 'repl.commands.watch',
        # ui
        'ui', 'ui.banner', 'ui.components', 'ui.console', 'ui.context_logs',
        'ui.dimming', 'ui.help', 'ui.markdown', 'ui.palette',
        'ui.repl_bindings', 'ui.slash_complete', 'ui.streaming', 'ui.tool_logs',
        # third-party
        'dotenv', 'tkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='llm-orchestrator-setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
