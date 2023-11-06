# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'python-dbusmock'
copyright = '2023, Martin Pitt'  # noqa: A001
author = 'Martin Pitt'

try:
    # created by setuptools_scm
    from dbusmock._version import __version__ as release
except ImportError:
    release = '0.git'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'myst_parser',
    'autoapi.extension',
]

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']


apidoc_module_dir = '../dbusmock'
apidoc_output_dir = '.'
apidoc_separate_modules = True
apidoc_excluded_paths = ['tests']

autoapi_dirs = ['../dbusmock']
autoapi_type = 'python'
autoapi_member_order = 'bysource'
autoapi_options = ['members', 'undoc-members', 'show-inheritance', 'show-module-summary', 'special-members', 'imported-members']
