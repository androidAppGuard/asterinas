#!/usr/bin/env python3

# SPDX-License-Identifier: MPL-2.0

"""
run.py - benchmark harness for aster-code-review.

Reads `benchmark/problems.yaml`.

The agent that BOTH reviews and grades is chosen by ACR_AGENT_PROFILE (required)
- see agent_profiles/.
The shared launcher (`../scripts/run_agent.py`) still does the agent launch,
but this harness inlines the skill overlay and headless prompt assembly
instead of shelling out to `overlay_skill.py` / `aster_code_review.py`
(see spec/benchmark.md, "Agent profiles").
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
import time
import yaml
from pipeline import run_review_pipeline


DEFAULT_REMOTE = "https://github.com/asterinas/asterinas"


HERE = Path(__file__).resolve().parent
REPO = Path(
    subprocess.check_output(
        ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()
)

SKILL = HERE.parent
RUN_AGENT = SKILL / "src" / "scripts" / "run_agent.py"


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    stdout=None,
    stderr=None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:

    print("consume ====","exec cmd: ",argv,"\n",flush=True)

    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=stdout,
        stderr=stderr,
        check=check,
    )


def rm_rf(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path, ignore_errors=True)


def overlay_skill(worktree: Path) -> int:
    skill = HERE.parent

    try:
        rm_rf(worktree / ".agents")
        rm_rf(worktree / ".claude")

        skill_parent = worktree / ".agents" / "skills"
        skill_parent.mkdir(parents=True, exist_ok=True)

        overlaid_skill = skill_parent / "aster-code-review"
        shutil.copytree(skill, overlaid_skill, symlinks=True)

        rm_rf(overlaid_skill / "benchmark")
        rm_rf(overlaid_skill / "guideline-root")

        guideline_parent = overlaid_skill / "guideline-root" / "book" / "src" / "to-contribute"
        guideline_parent.mkdir(parents=True, exist_ok=True)
        guideline_src = (
            REPO / "book" / "src" / "to-contribute" / "coding-guidelines"
        )
        shutil.copytree(guideline_src, guideline_parent / "coding-guidelines", symlinks=True)

        claude_skills = worktree / ".claude" / "skills"
        claude_skills.mkdir(parents=True, exist_ok=True)
        link = claude_skills / "aster-code-review"
        rm_rf(link)
        os.symlink("../../.agents/skills/aster-code-review", link)
    except OSError as exc:
        eprint(f"overlay_skill: {exc}")
        return 1

    return 0


def build_arg_string(argv: list[str]) -> str:
    args = ""
    for token in argv:
        if '"' in token:
            raise ValueError(f"a double quote in an argument is not supported: {token}")
        if any(ch.isspace() for ch in token):
            token = f'"{token}"'
        args = f"{args} {token}" if args else token
    return args


def build_review_prompt(skillargs: str) -> str:
    return f"Use the aster-code-review skill with these arguments: {skillargs}. Review this working tree."


def launch_review_agent(worktree: Path, skillargs: str, env: dict[str, str]) -> int:
    print("consume ====","launch_review_agent: ",worktree, skillargs,"\n",flush=True)
    review_skill = worktree / ".agents" / "skills" / "aster-code-review"
    if not review_skill.is_dir():
        review_skill = SKILL
    try:
        run_review_pipeline(skillargs, repo=worktree, skill=review_skill, env=env)
    except Exception as exc:
        eprint(f"run.py: {exc}")
        return 1
    return 0


if not os.environ.get("ACR_AGENT_PROFILE"):
    eprint(
        "run.py: ACR_AGENT_PROFILE is required (e.g. ACR_AGENT_PROFILE=codex); "
        "run_agent.py lists available profiles"
    )
    sys.exit(2)


WORK_IS_TEMP = False
if os.environ.get("WORK"):
    WORK = Path(os.environ["WORK"])
else:
    WORK = Path(tempfile.mkdtemp())
    WORK_IS_TEMP = True
WORK.mkdir(parents=True, exist_ok=True)

# Ground truth and the guideline tree live OUTSIDE the worktree parent,
# so a review can never reach them by walking up from its own worktree.
SPEC = Path(tempfile.mkdtemp())
GROOT = Path(tempfile.mkdtemp())
(GROOT / "book" / "src" / "to-contribute").mkdir(parents=True, exist_ok=True)
guidelines_src = REPO / "book" / "src" / "to-contribute" / "coding-guidelines"
guidelines_dst = GROOT / "book" / "src" / "to-contribute" / "coding-guidelines"
if guidelines_src.exists():
    try:
        shutil.copytree(guidelines_src, guidelines_dst)
    except OSError:
        pass


KEEP_DIR: Path | None = None
if os.environ.get("KEEP_REVIEWS"):
    if os.environ["KEEP_REVIEWS"] == "1":
        KEEP_DIR = Path(tempfile.mkdtemp())
    else:
        KEEP_DIR = Path(os.environ["KEEP_REVIEWS"])
        KEEP_DIR.mkdir(parents=True, exist_ok=True)


def cleanup() -> None:
    proc = run(
        ["git", "-C", str(REPO), "worktree", "list", "--porcelain"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    for line in proc.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        wt = line.removeprefix("worktree ")
        if wt.startswith(str(WORK) + os.sep):
            run(
                ["git", "-C", str(REPO), "worktree", "remove", "--force", wt],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    run(
        ["git", "-C", str(REPO), "worktree", "prune"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    shutil.rmtree(SPEC, ignore_errors=True)
    shutil.rmtree(GROOT, ignore_errors=True)
    if WORK_IS_TEMP:
        shutil.rmtree(WORK, ignore_errors=True)


atexit.register(cleanup)


def keep_reviews(problem_id: str, wt: Path) -> None:
    if KEEP_DIR is None:
        return

    dst = KEEP_DIR / problem_id
    dst.mkdir(parents=True, exist_ok=True)

    copies = [
        (Path(str(wt) + ".off.md"), dst / "review.md"),
        (Path(str(wt) + ".on.md"), dst / "review-fanout.md"),
        (Path(str(wt) + ".review.md"), dst / "review.md"),
        (SPEC / f"{problem_id}.defects.txt", dst / "expected-defects.txt"),
        (SPEC / f"{problem_id}.negatives.txt", dst / "expected-negatives.txt"),
    ]
    for src, target in copies:
        if src.is_file() and (src.stat().st_size > 0 or src.parent == SPEC):
            shutil.copy2(src, target)


def validate_problem_yaml() -> None:
    proc = run(
        [str(HERE / "../benchmark/validate_problem_yaml.sh")],
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    if proc.returncode != 0:
        eprint("run.py: problems.yaml failed validation; aborting")
        sys.exit(2)


def defect_block(defect: dict, number: int) -> str:
    target = defect["target"]
    loc = target.get("path") or ("<" + target["kind"] + ">")
    if target.get("lines"):
        loc += " lines " + str(target["lines"])

    desc = " ".join(str(defect["desc"]).split())
    expect = " ".join(str(defect["expectation"]).split())
    return (
        f"{number}. location: {loc} "
        f"(persona: {defect['persona']}, grounding: {defect['grounding']}, "
        f"severity: {defect['severity']})\n"
        f"   defect: {desc}\n"
        f"   MATCH IF: {expect}"
    )


def emit() -> list[tuple[str, str, str, str, str, int, int]]:
    docs = yaml.safe_load((HERE / "../benchmark/problems.yaml").read_text())
    index = []

    for problem in docs:
        problem_id = problem["problem_id"]
        review_mode = problem["review_mode"]
        reals = [d for d in problem["defects"] if not d.get("is_negative")]
        negs = [d for d in problem["defects"] if d.get("is_negative")]

        (SPEC / f"{problem_id}.defects.txt").write_text(
            "# Expected defects\n\n"
            + "\n\n".join(defect_block(d, i + 1) for i, d in enumerate(reals))
            + "\n"
        )
        if negs:
            (SPEC / f"{problem_id}.negatives.txt").write_text(
                "# Must NOT be flagged (false-positive traps)\n\n"
                + "\n\n".join(defect_block(d, i + 1) for i, d in enumerate(negs))
                + "\n"
            )

        checkout = problem["commit"]
        remote = problem.get("remote", DEFAULT_REMOTE)
        if "diff" in review_mode:
            mode = "diff"
            arg = review_mode["diff"]["base"]
        else:
            mode = "files"
            arg = " ".join(review_mode["files"])

        index.append((problem_id, mode, checkout, remote, arg, len(reals), len(negs)))

    return index


def default_review(worktree: Path, output: Path, skillargs: str) -> int:
    if overlay_skill(worktree) != 0:
        return 1

    env = os.environ.copy()
    env["ACR_GUIDELINE_ROOT"] = str(GROOT)
    suffix = build_arg_string([str(output), "--overwrite"])
    return launch_review_agent(worktree, f"{skillargs} {suffix}", env)


GRADE_PROMPT = """You are grading a code review. The expected defects are in {defects_file}. The produced review is in {review}.

  Task:
  Count how many expected defects were caught by the produced review.
  Each expected defect has:
    - Location: the target file path or commit-message locus, optionally with line(s)
    - Persona
    - MATCH IF: the authoritative matching criterion
  For each expected defect, decide whether ANY single produced review comment catches that defect. A review comment is considered a match only if all of the following conditions are satisfied
     - Match defect location: The file path of the defect must match. If the expected defect has a line range, the
     produced comment's defect line range should contain the expected defect's actual line range.
     - Match defect persona: The defect persona (\\e.g., security, development,maintainability,hardware,documentation) must match. If the persona in expected defect is development, the persona in produced review must be persona.
     - Match defect description: The description must match the specific problem (e.g., "memory leak in function
     X", "out of memory", "missing lock").
  Output:
  Respond with ONLY two space-separated integers, caught then total, and nothing else (for example: 1 2)."""

NEG_GRADE_PROMPT = """The items in {negatives_file} are false-positive traps that a correct review must NOT raise as real defects. Read the review {review}. Output ONLY PASS (none raised) or FAIL (at least one raised)."""


def command_output(argv: list[str]) -> str:
    proc = run(argv, stdout=subprocess.PIPE, stderr=None)
    return proc.stdout.strip()


def default_grade(defects_file: Path, review: Path) -> str:
    return command_output(
        [
            str(RUN_AGENT),
            GRADE_PROMPT.format(defects_file=defects_file, review=review),
        ]
    )


def default_neg_grade(negatives_file: Path, review: Path) -> str:
    return command_output(
        [
            str(RUN_AGENT),
            NEG_GRADE_PROMPT.format(negatives_file=negatives_file, review=review),
        ]
    )


def review_cmd(worktree: Path, output: Path, skillargs: str) -> int:
    override = os.environ.get("REVIEW_CMD")
    if not override or override == "default_review":
        return default_review(worktree, output, skillargs)

    proc = run(
        [override, str(worktree), str(output), skillargs],
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    return proc.returncode


def grade_cmd(defects_file: Path, review: Path) -> str:
    override = os.environ.get("GRADE_CMD")
    if not override or override == "default_grade":
        return default_grade(defects_file, review)

    return command_output([override, str(defects_file), str(review)])


def neg_grade_cmd(negatives_file: Path, review: Path) -> str:
    override = os.environ.get("NEG_GRADE_CMD")
    if not override or override == "default_neg_grade":
        return default_neg_grade(negatives_file, review)

    return command_output([override, str(negatives_file), str(review)])


def selected(problem_id: str) -> bool:
    selectors = os.environ.get("PROBLEMS", "").split()
    if not selectors:
        return True
    return any(problem_id == token or problem_id.startswith(token) for token in selectors)


def parse_two_fields(value: str) -> tuple[str, str]:
    fields = value.split(maxsplit=1)
    if not fields:
        return "", ""
    if len(fields) == 1:
        return fields[0], ""
    return fields[0], fields[1]


def is_uint(value: str) -> bool:
    return re.fullmatch(r"[0-9]+", value or "") is not None


def run_one(
    wt: Path,
    problem_id: str,
    mode: str,
    checkout: str,
    remote: str,
    arg: str,
    nreal: int,
    nneg: int,
    min_recall: int,
) -> str | None:
    rm_rf(wt)

    if mode == "diff":
        exists = run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{checkout}^{{commit}}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exists.returncode != 0:
            fetch = run(
                ["git", "-C", str(REPO), "fetch", "--no-tags", remote, checkout],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if fetch.returncode != 0:
                return None

        add = run(
            [
                "git",
                "-C",
                str(REPO),
                "worktree",
                "add",
                "-f",
                "--detach",
                str(wt),
                checkout,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if add.returncode != 0:
            return None

        base = run(
            ["git", "-C", str(wt), "rev-parse", arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if base.returncode != 0:
            return None
        skillargs = f"diff {base.stdout.strip()}"
    else:
        add = run(
            [
                "git",
                "-C",
                str(REPO),
                "worktree",
                "add",
                "-f",
                "--detach",
                str(wt),
                checkout,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if add.returncode != 0:
            return None
        skillargs = f"files {arg}"

    if min_recall == 0:
        out = Path(str(wt) + ".off.md")
        out.unlink(missing_ok=True)
        if review_cmd(wt, out, f"{skillargs} --per-persona-context=no") != 0:
            return None
        if not out.is_file() or out.stat().st_size == 0:
            return None
        return "PROD"

    if nreal == 0 and nneg > 0:
        out = Path(str(wt) + ".review.md")
        out.unlink(missing_ok=True)
        if review_cmd(wt, out, f"{skillargs} --per-persona-context=yes") != 0:
            return None
        if not out.is_file() or out.stat().st_size == 0:
            return None
        return f"NEG {neg_grade_cmd(SPEC / f'{problem_id}.negatives.txt', out)}"

    defects_file = SPEC / f"{problem_id}.defects.txt"
    off = Path(str(wt) + ".off.md")
    off.unlink(missing_ok=True)
    if review_cmd(wt, off, f"{skillargs} --per-persona-context=no") != 0:
        return None
    if not off.is_file() or off.stat().st_size == 0:
        return None

    caught, total = parse_two_fields(grade_cmd(defects_file, off))
    if is_uint(caught) and is_uint(total) and caught == total and int(total) > 0:
        return f"OFF {caught} {total}"

    on = Path(str(wt) + ".on.md")
    on.unlink(missing_ok=True)
    if review_cmd(wt, on, f"{skillargs} --per-persona-context=yes") != 0:
        return None
    if not on.is_file() or on.stat().st_size == 0:
        return None
    return f"ON {grade_cmd(defects_file, on)}"


def shell_quote(value: str) -> str:
    return shlex.quote(value)


def main() -> int:
    validate_problem_yaml()
    try:
        min_recall = int(os.environ.get("MIN_RECALL", "100"))
    except ValueError:
        raise SystemExit("run.py: MIN_RECALL must be an integer")

    total_caught = 0
    total_defects = 0
    problems = 0
    off_ok = 0
    escalated = 0
    neg_pass = 0
    neg_total = 0
    n = 0
    harness_errors = 0
    produced = 0

    problem_array = emit()
    for problem_id, mode, checkout, remote, arg, nreal, nneg in problem_array:
        print("consume ====",problem_id, mode, checkout, remote, arg, nreal, nneg,"\n",flush=True)
        if not selected(problem_id):
            continue

        n += 1
        wt = WORK / f"wt{n}"
        result = run_one(
            wt,
            problem_id,
            mode,
            checkout,
            remote,
            arg,
            nreal,
            nneg,
            min_recall,
        )
        if result is None:
            keep_reviews(problem_id, wt)
            print(f"{problem_id:<34}  ?  (harness error — setup/review failed)")
            harness_errors += 1
            continue

        keep_reviews(problem_id, wt)
        if result == "PROD":
            produced += 1
            print(f"{problem_id:<34} produced ✓")
        elif result.startswith("NEG "):
            verdict = result.removeprefix("NEG ")
            neg_total += 1
            if "PASS" in verdict:
                neg_pass += 1
            print(f"{problem_id:<34} precision {verdict}")
        elif result.startswith("OFF ") or result.startswith("ON "):
            tier = result.split(" ", 1)[0]
            caught, defects = parse_two_fields(result.split(" ", 1)[1])
            if not (is_uint(caught) and is_uint(defects)):
                print(
                    f"{problem_id:<34} recall  ?/?  "
                    f"(unparseable grader output: {shell_quote(result)})"
                )
                harness_errors += 1
                continue

            problems += 1
            total_caught += int(caught)
            total_defects += int(defects)
            if tier == "OFF":
                off_ok += 1
                label = "combined"
            else:
                escalated += 1
                label = "fan-out"
            print(f"{problem_id:<34} recall {caught}/{defects} [{label}]")
        else:
            print(
                f"{problem_id:<34} recall  ?/?  "
                f"(unexpected: {shell_quote(result)})"
            )
            harness_errors += 1

    print("----")
    if KEEP_DIR is not None:
        print(
            "reviews kept for inspection in: "
            f"{KEEP_DIR}  (per problem: review.md + expected-defects.txt)"
        )

    if min_recall == 0:
        print(f"smoke: {produced}/{n} reviews produced; harness errors: {harness_errors}")
        return 0 if harness_errors == 0 and produced > 0 else 1

    recall_pct = 0
    if total_defects > 0:
        recall_pct = 100 * total_caught // total_defects

    print(
        "recall: "
        f"{total_caught}/{total_defects} ({recall_pct}%, gate >={min_recall}%) "
        f"across {problems} problems; per-persona-context: {off_ok} combined, "
        f"{escalated} fan-out; precision: {neg_pass}/{neg_total} clean; "
        f"harness errors: {harness_errors}"
    )

    passed = True
    if harness_errors > 0:
        passed = False
    if neg_pass != neg_total:
        passed = False
    if recall_pct < min_recall:
        passed = False
    if total_defects == 0:
        passed = False
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
