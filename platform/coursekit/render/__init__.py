"""Turning a course into the one HTML file the reader opens.

    bundler    the front end: the CSS and JS named by web/bundle.json, concatenated
    renderer   DATA + CFG injected into the shell; writes the published and local copies

Two modules, because the front end is assembled whether or not a course is being built —
`build.py check` reads the bundle's inventory without rendering anything.
"""
