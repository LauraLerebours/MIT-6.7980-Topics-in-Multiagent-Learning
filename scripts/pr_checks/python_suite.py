"""Record individual unittest results so baseline failures cannot hide new ones."""
import json
from pathlib import Path
import sys
import unittest

root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'scripts'))
suite=unittest.defaultTestLoader.discover(str(root/'scripts'),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=1).run(suite)
Path(sys.argv[2]).write_text(json.dumps(dict(run=result.testsRun,
    failures=[dict(test=test.id(),detail=detail) for test,detail in result.failures+result.errors],
    skipped=[dict(test=test.id(),reason=reason) for test,reason in result.skipped]),indent=2))
sys.exit(not result.wasSuccessful())
