"""Pytest bootstrap that runs before any ``meals`` import.

The application reads ``DATABASE_URL`` when its module-level engine is created
(``meals.database.session``), so the test database must be redirected *before*
``meals`` is imported. Pytest loads this root-level ``conftest.py`` before
``tests/conftest.py``, which guarantees the suite can never open a real
``meals.db``. See TODO -> "Protect the live data".
"""

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
