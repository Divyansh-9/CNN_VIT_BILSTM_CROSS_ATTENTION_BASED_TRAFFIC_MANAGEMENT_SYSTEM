"""Cross-component contracts.

Top level rather than inside `mfstnet/`, because these are shared by `edge/`,
`server/` and `dashboard/` — none of which is the model. PRD §22.3 does not list
this package; the alternative was to duplicate the schema in three places, which
is the failure this package exists to prevent.
"""
