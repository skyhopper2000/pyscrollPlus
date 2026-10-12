"""Sphinx configuration for the pyscroll documentation."""

from __future__ import annotations

import datetime
import os
import sys

# Import pyscroll straight from the source tree, so the docs never depend on
# an installed copy (and Read the Docs does not need to build the package).
sys.path.insert(0, os.path.abspath(".."))

import pyscroll  # noqa: E402


def _format_version(value) -> str:
    """``pyscroll.__version__`` has been both a tuple and a string."""
    if isinstance(value, (tuple, list)):
        return ".".join(str(part) for part in value)
    return str(value)


# -- Project information -----------------------------------------------------

project = "pyscroll"
author = "bitcraft and contributors"
copyright = f"2014-{datetime.date.today().year}, bitcraft and contributors"
release = _format_version(pyscroll.__version__)
version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "myst_parser",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

# -- autodoc / napoleon ------------------------------------------------------

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
# Show the class docstring and the __init__ docstring (which holds the
# constructor arguments) together.
autoclass_content = "both"
# PyscrollGroup.__init__ would otherwise inherit pygame's LayeredUpdates
# docstring, which is not valid reST.
autodoc_inherit_docstrings = False

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False

# -- intersphinx -------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pygame": ("https://pyga.me/docs/", None),
}

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = f"pyscroll {release}"
html_theme_options = {
    "source_repository": "https://github.com/skyhopper2000/pyscrollPlus",
    "source_branch": "master",
    "source_directory": "docs/",
}
