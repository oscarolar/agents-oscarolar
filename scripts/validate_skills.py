#!/usr/bin/env python3
"""Structural validation for every skill under skills/.

Checks (mirrors the governance rules in README.md / each skill's own
standards, kept intentionally dependency-free so it runs anywhere):

- directory name uses hyphens, never underscores
- SKILL.md exists with YAML frontmatter containing name, category, description
- description starts with "Use this skill when" and contains "Triggers on:"
- evals/evals.json exists, is valid JSON, and has at least 2 cases
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"


def parse_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return None
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def validate_skill(skill_dir):
    errors = []
    name = skill_dir.name

    if "_" in name:
        errors.append(f"{name}: directory name must use hyphens, not underscores")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{name}: missing SKILL.md")
        return errors

    frontmatter = parse_frontmatter(skill_md.read_text())
    if frontmatter is None:
        errors.append(f"{name}: SKILL.md has no YAML frontmatter")
        return errors

    for field in ("name", "category", "description"):
        if field not in frontmatter:
            errors.append(f"{name}: frontmatter missing '{field}'")

    description = frontmatter.get("description", "")
    if not description.startswith("Use this skill when"):
        errors.append(f"{name}: description must start with 'Use this skill when'")
    if "Triggers on:" not in description:
        errors.append(f"{name}: description must include a 'Triggers on:' clause")

    evals_json = skill_dir / "evals" / "evals.json"
    if not evals_json.exists():
        errors.append(f"{name}: missing evals/evals.json")
    else:
        try:
            data = json.loads(evals_json.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: evals.json is not valid JSON ({exc})")
        else:
            cases = data.get("evals", [])
            if len(cases) < 2:
                errors.append(f"{name}: evals.json needs at least 2 cases, found {len(cases)}")

    return errors


def main():
    if not SKILLS_DIR.exists():
        print("No skills/ directory found - nothing to validate.")
        return 0

    all_errors = []
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        all_errors.extend(validate_skill(skill_dir))

    if all_errors:
        print("Skill validation failed:")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print(f"All skills under {SKILLS_DIR} passed structural validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
