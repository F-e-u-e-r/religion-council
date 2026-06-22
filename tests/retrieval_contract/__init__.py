# Marks tests/retrieval_contract/ as a package so `python -m unittest discover -s tests`
# recurses into it (a subdirectory without __init__.py is skipped by discovery on Python 3.9).
# The shared battery lives in contract_assertions.py; the two test modules import it via a
# sys.path insert so they also run under direct execution.
