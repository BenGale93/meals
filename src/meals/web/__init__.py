"""The website for meals app.

Every page module **must** be imported here: importing it is what registers the
page and its route with :class:`meals.web.core.PageRegistry`. The navigation
order is defined by :data:`meals.web.core.PAGES`, not by the order of these
imports, and ``PageRegistry.validate()`` fails start-up if a page declared in
``PAGES`` has no imported module.
"""

from meals.web import index, new, planner, timings  # noqa: F401
