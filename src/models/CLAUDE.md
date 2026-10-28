# models/

Every class in this package is re-exported from `__init__.py`, so callers write `from models import X`.

Whenever a class is added to, removed from, or renamed in any module here (by the user or by Claude),
update `__init__.py` in the same turn, without asking first:

- the `from .<module> import (...)` block for that module;
- `__all__`, kept in alphabetical order.

Then check with `python -m ruff check models` and an import (`python -c "from models import X"`), run
from `src/`, and say in one line what changed.
