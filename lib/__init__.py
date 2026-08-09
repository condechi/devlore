"""devlore shared machinery.

Lives at ``~/.devlore/lib/`` — a single copy for every KB the user manages.
KB-local scripts in ``<kb>/scripts/`` import shared modules from here via
``PYTHONPATH=~/.devlore/lib`` (set by the launcher). The active KB is resolved
through the ``DEVLORE_KB_ROOT`` env var, so one shared ``config.py`` serves all
KBs at call time.
"""