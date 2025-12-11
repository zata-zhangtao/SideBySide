import os
import sys

# Ensure this tests folder is importable first, so that
# `import llm_api_loader` resolves to the test-local copy here.
_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

