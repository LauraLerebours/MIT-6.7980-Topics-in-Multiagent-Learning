"""Check integration, course-wide source consistency, and existing regressions."""
from pathlib import Path
import json
import sys

from common import arguments, command, finish, prepare, run_check


def main():
    args, report = arguments("prescreen")
    try:
        before, after = prepare(args, report)
        if after:
            for side, root in (("before", before), ("after", after)):
                run_check(report, args.output, "course-consistency", side,
                          [sys.executable, str(Path(__file__).with_name("source_probe.py")), str(root)], root)
                run_check(report, args.output, "python-regressions", side,
                          [sys.executable, str(Path(__file__).with_name('python_suite.py')), str(root), str(args.output/f'{side}-tests.json')],
                          root, timeout=1200)
            baseline = {x["name"]: x for x in report["checks"] if x["side"] == "before"}
            for check in (x for x in report["checks"] if x["side"] == "after" and x["status"] == "fail"):
                if check['name']=='python-regressions' and all((args.output/f'{side}-tests.json').is_file() for side in ('before','after')):
                    old=json.loads((args.output/'before-tests.json').read_text())
                    new=json.loads((args.output/'after-tests.json').read_text())
                    previous={x['test'] for x in old['failures']}
                    for failure in new['failures']:
                        inherited=failure['test'] in previous
                        report['findings'].append(dict(level='warning' if inherited else 'error',code='python-regression',page='',inherited=inherited,
                            message=failure['test']+': '+failure['detail'].strip().splitlines()[-1]))
                    continue
                inherited = baseline[check["name"]]["status"] == "fail"
                report["findings"].append(dict(level="warning" if inherited else "error", inherited=inherited, code=check["name"], page="",
                    message=f"{check['name']} failed. " + ("The same check also fails on the target branch; inspect both logs to distinguish additional failures." if inherited else "This check passes on the target branch.") + f" See {check['log']}."))
            status, log = command(["git", "-C", str(after), "diff", "--check", args.base, "HEAD"])
            (args.output / "whitespace.log").write_text(log, encoding="utf-8")
            if status:
                report["findings"].append(dict(level="warning", code="whitespace", page="", message="Changed lines contain whitespace errors; see whitespace.log."))
            report["coverage"]["source"] = "Merge conflicts, syllabus/header consistency, configured assets, cross-lecture labels, and the repository's Python regression suite. Exporter Rust tests run in HTML review."
    except Exception as error:
        report["findings"].append(dict(level="error", code="check-incomplete", page="", message=str(error)[:1000]))
    return finish(args, report)


if __name__ == "__main__":
    sys.exit(main())
