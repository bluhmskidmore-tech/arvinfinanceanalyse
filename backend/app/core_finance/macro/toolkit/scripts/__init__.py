"""Migrated macro toolkit scripts.

Scripts in this package are executed through
``app.core_finance.macro.toolkit.run_toolkit_script`` so their legacy
``paths`` imports keep working. Package imports keep vendor compatibility
shims local to each script instead of mutating process-wide ``sys.path`` or
``sys.modules``.
"""
