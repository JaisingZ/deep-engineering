#!/usr/bin/env python3
"""按 skills/human-writing-style/config/style-rules.md 检查一篇 Markdown。

只使用 Python 标准库。退出码：0 通过，1 有违规，2 是用法或配置错误。

    python3 skills/human-writing-style/scripts/lint.py path/to/article.md
    python3 skills/human-writing-style/scripts/lint.py path/to/article.md --rules path/to/style-rules.md
    python3 skills/human-writing-style/scripts/lint.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_RULES = HERE.parent / "config" / "style-rules.md"

FENCE_RE = re.compile(r"```lint\s+(\S+)\s*\n(.*?)```", re.S)
HAN_RE = re.compile(r"[\u4e00-\u9fff]")
SENTENCE_END_RE = re.compile(r"[。！？!?]")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
BOLD_LABEL_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+\*\*[^*\n]+\*\*\s*[:：]"
)
HEADING_RE = re.compile(r"^#{1,6}\s+\S")
IMAGE_RE = re.compile(r"^!\[[^\]]*\]\([^)]*\)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
TABLE_RE = re.compile(r"^\s*\|.+\|\s*$")
# 表情、杂项符号、装饰符号、区域旗帜。变体选择符和零宽连接符跟着表情一起吃掉。
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U0001F1E6-\U0001F1FF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "\uFE0F"
    "\u200D"
    "]+"
)

THRESHOLD_KEYS = (
    "bold_max",
    "emoji_max",
    "paragraph_han_max",
    "meme_max",
    "ending_han_max",
    "ending_sentences_max",
    "chain_min_distinct",
    "stack_opener_min",
)

LIST_FENCES = (
    "banned",
    "colloquial-banned",
    "colloquial-allowed",
    "memes",
    "chain-anchors",
    "chain-markers",
    "emoji",
)


@dataclass
class Rules:
    bold_max: int
    emoji_max: int
    paragraph_han_max: int
    meme_max: int
    ending_han_max: int
    ending_sentences_max: int
    chain_min_distinct: int
    stack_opener_min: int
    banned: list[str]
    colloquial_banned: list[str]
    colloquial_allowed: list[str]
    memes: list[str]
    chain_anchors: list[str]
    chain_markers: list[str]
    stacking: list[list[str]]
    emoji_literals: list[str]
    source: str


@dataclass
class Violation:
    kind: str
    line: int | None
    message: str


@dataclass
class Report:
    path: str
    rules_path: str
    rules: Rules
    prose_paragraphs: int = 0
    bold_count: int = 0
    emoji_count: int = 0
    meme_count: int = 0
    long_paragraphs: int = 0
    banned_hits: int = 0
    chain_hit: bool = False
    stacking_hits: int = 0
    violations: list[Violation] = field(default_factory=list)


class ConfigError(Exception):
    pass


def parse_rules(path: Path) -> Rules:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"读不到规则文件：{path}（{exc}）") from exc

    fences: dict[str, str] = {}
    for name, body in FENCE_RE.findall(text):
        if name in fences:
            raise ConfigError(f"规则文件里有重复的 lint 围栏：{name}")
        fences[name] = body

    missing = [name for name in ("thresholds", *LIST_FENCES, "stacking") if name not in fences]
    if missing:
        raise ConfigError("规则文件缺少 lint 围栏：" + "、".join(missing))

    values: dict[str, int] = {}
    for raw in _lines(fences["thresholds"]):
        if ":" not in raw:
            raise ConfigError(f"阈值行缺少冒号：{raw}")
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if key not in THRESHOLD_KEYS:
            raise ConfigError(f"未知阈值：{key}")
        try:
            values[key] = int(value)
        except ValueError as exc:
            raise ConfigError(f"阈值 {key} 不是整数：{value}") from exc
    absent = [key for key in THRESHOLD_KEYS if key not in values]
    if absent:
        raise ConfigError("阈值缺少：" + "、".join(absent))

    lists = {name: _lines(fences[name]) for name in LIST_FENCES}
    for name, items in lists.items():
        if not items:
            raise ConfigError(f"lint 围栏是空的：{name}")

    stacking: list[list[str]] = []
    for raw in _lines(fences["stacking"]):
        tokens = raw.split()
        if len(tokens) < 2:
            raise ConfigError(f"叠加规则至少要两个词：{raw}")
        stacking.append(tokens)
    if not stacking:
        raise ConfigError("lint 围栏是空的：stacking")

    return Rules(
        bold_max=values["bold_max"],
        emoji_max=values["emoji_max"],
        paragraph_han_max=values["paragraph_han_max"],
        meme_max=values["meme_max"],
        ending_han_max=values["ending_han_max"],
        ending_sentences_max=values["ending_sentences_max"],
        chain_min_distinct=values["chain_min_distinct"],
        stack_opener_min=values["stack_opener_min"],
        banned=lists["banned"],
        colloquial_banned=lists["colloquial-banned"],
        colloquial_allowed=lists["colloquial-allowed"],
        memes=lists["memes"],
        chain_anchors=lists["chain-anchors"],
        chain_markers=lists["chain-markers"],
        stacking=stacking,
        emoji_literals=lists["emoji"],
        source=str(path),
    )


def _lines(body: str) -> list[str]:
    items = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        items.append(line)
    return items


def meaningful_lines(text: str) -> list[tuple[int, str]]:
    """去掉文首 YAML 和围栏代码，保留原始行号。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    total = len(lines)
    if total and lines[0].strip() == "---":
        index = 1
        while index < total and lines[index].strip() != "---":
            index += 1
        index += 1
    in_fence = False
    kept: list[tuple[int, str]] = []
    for cursor in range(index, total):
        line = lines[cursor]
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        kept.append((cursor + 1, line))
    return kept


def blocks_of(lines: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    grouped: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for item in lines:
        if item[1].strip() == "":
            if current:
                grouped.append(current)
                current = []
            continue
        current.append(item)
    if current:
        grouped.append(current)
    return grouped


def is_prose(block: list[tuple[int, str]]) -> bool:
    for _, line in block:
        stripped = line.strip()
        if not stripped:
            continue
        if HEADING_RE.match(stripped) or IMAGE_RE.match(stripped):
            continue
        if LIST_RE.match(line) or TABLE_RE.match(stripped):
            continue
        return True
    return False


def han_count(text: str) -> int:
    return len(HAN_RE.findall(text))


def find_terms(text: str, terms: list[str]) -> list[tuple[int, int, str]]:
    """更长的词优先。同一段字符只记一次。"""
    occupied = [False] * len(text)
    found: list[tuple[int, int, str]] = []
    for term in sorted(terms, key=len, reverse=True):
        if term.isascii():
            haystack = text.lower()
            needle = term.lower()
        else:
            haystack = text
            needle = term
        start = 0
        while True:
            at = haystack.find(needle, start)
            if at < 0:
                break
            end = at + len(needle)
            if not any(occupied[at:end]):
                for pos in range(at, end):
                    occupied[pos] = True
                found.append((at, end, term))
            start = at + max(len(needle), 1)
    found.sort()
    return found


def emoji_spans(text: str, literals: list[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    occupied = [False] * len(text)
    for match in EMOJI_RE.finditer(text):
        raw = match.group(0)
        core = raw.replace("\uFE0F", "").replace("\u200D", "").strip()
        if not core:
            continue
        spans.append((match.start(), match.end(), raw))
        for pos in range(match.start(), match.end()):
            occupied[pos] = True
    for literal in literals:
        start = 0
        while True:
            at = text.find(literal, start)
            if at < 0:
                break
            end = at + len(literal)
            if not any(occupied[at:end]):
                spans.append((at, end, literal))
                for pos in range(at, end):
                    occupied[pos] = True
            start = at + max(len(literal), 1)
    spans.sort()
    return spans


def ladder_hit(text: str, tokens: list[str]) -> bool:
    """第三档要另起一句，避免把「而且更好」里的「更」算成叠加。"""
    if len(tokens) < 3:
        return False
    first, second, third = (re.escape(token) for token in tokens[:3])
    pattern = re.compile(
        first
        + r".{0,80}?"
        + second
        + r".{0,80}?(?:[，,、；;].{0,24}?"
        + third
        + r"|"
        + third
        + r"是)"
    )
    return pattern.search(text) is not None


def excerpt(text: str, limit: int = 36) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= limit:
        return flat
    return flat[:limit] + "…"


def show_path(path: str) -> str:
    try:
        return Path(path).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path


def lint_text(text: str, rules: Rules, path: str = "<memory>") -> Report:
    report = Report(path=path, rules_path=rules.source, rules=rules)
    lines = meaningful_lines(text)
    grouped = blocks_of(lines)
    prose = [block for block in grouped if is_prose(block)]
    report.prose_paragraphs = len(prose)

    bold_lines: list[int] = []
    emoji_hits: list[tuple[int, str]] = []
    meme_hits: list[tuple[int, str]] = []
    banned_hits: list[tuple[int, str, str]] = []
    label_lines: list[int] = []
    marker_lines: dict[str, list[int]] = {marker: [] for marker in rules.chain_markers}

    for lineno, line in lines:
        visible = INLINE_CODE_RE.sub("", line)
        bolds = list(BOLD_RE.finditer(visible))
        if bolds:
            report.bold_count += len(bolds)
            bold_lines.append(lineno)
        if BOLD_LABEL_RE.match(visible):
            label_lines.append(lineno)
        for _, _, literal in emoji_spans(visible, rules.emoji_literals):
            report.emoji_count += 1
            emoji_hits.append((lineno, literal))
        for _, _, term in find_terms(visible, rules.memes):
            report.meme_count += 1
            meme_hits.append((lineno, term))
        for _, _, term in find_terms(visible, rules.banned):
            report.banned_hits += 1
            banned_hits.append((lineno, term, "禁用词"))
        for _, _, term in find_terms(visible, rules.colloquial_banned):
            report.banned_hits += 1
            banned_hits.append((lineno, term, "口语"))
        for marker in rules.chain_markers:
            if marker in visible:
                marker_lines[marker].append(lineno)

    present = [marker for marker, spots in marker_lines.items() if spots]
    anchors_present = [marker for marker in rules.chain_anchors if marker_lines.get(marker)]
    if anchors_present and len(present) >= rules.chain_min_distinct:
        report.chain_hit = True
        detail = "、".join(f"{marker}（第 {marker_lines[marker][0]} 行）" for marker in present)
        report.violations.append(
            Violation("chain", marker_lines[present[0]][0], f"连接词链：{detail}")
        )

    for block in prose:
        body = "".join(line for _, line in block)
        start = block[0][0]
        count = han_count(body)
        if count > rules.paragraph_han_max:
            report.long_paragraphs += 1
            report.violations.append(
                Violation(
                    "paragraph",
                    start,
                    f"段长第 {start} 行：{count} 个汉字，上限 {rules.paragraph_han_max}。{excerpt(body)}",
                )
            )
        for ladder in rules.stacking:
            opener = ladder[0]
            opener_count = body.count(opener)
            full = ladder_hit(body, ladder)
            repeated = opener_count >= rules.stack_opener_min
            if not full and not repeated:
                continue
            report.stacking_hits += 1
            if full and repeated:
                why = f"「{'…'.join(ladder)}」按顺序出现，且「{opener}」有 {opener_count} 次"
            elif full:
                why = f"「{'…'.join(ladder)}」按顺序出现在同一段"
            else:
                why = f"「{opener}」在同一段出现 {opener_count} 次"
            report.violations.append(Violation("stacking", start, f"层层叠加第 {start} 行：{why}"))

    if prose:
        last = prose[-1]
        body = "".join(line for _, line in last)
        start = last[0][0]
        sentences = len(SENTENCE_END_RE.findall(body))
        hans = han_count(body)
        problems = []
        if sentences > rules.ending_sentences_max:
            problems.append(f"{sentences} 句，上限 {rules.ending_sentences_max} 句")
        if hans > rules.ending_han_max:
            problems.append(f"{hans} 个汉字，上限 {rules.ending_han_max}")
        if problems:
            report.violations.append(
                Violation(
                    "ending",
                    start,
                    "收尾第 {} 行：{}。{}".format(start, "；".join(problems), excerpt(body)),
                )
            )

    if report.bold_count > rules.bold_max:
        shown = "、".join(str(n) for n in bold_lines[:8])
        extra = f" 等 {len(bold_lines)} 行" if len(bold_lines) > 8 else ""
        report.violations.append(
            Violation(
                "bold",
                bold_lines[0] if bold_lines else None,
                f"加粗 {report.bold_count} 处，上限 {rules.bold_max}（第 {shown} 行{extra}）",
            )
        )
    for lineno in label_lines:
        report.violations.append(
            Violation("bold_label", lineno, f"加粗标签列表第 {lineno} 行：列表项以加粗词加冒号开头")
        )
    if report.emoji_count > rules.emoji_max:
        for lineno, literal in emoji_hits[:20]:
            report.violations.append(
                Violation("emoji", lineno, f"emoji 第 {lineno} 行：{literal}")
            )
        if len(emoji_hits) > 20:
            report.violations.append(
                Violation("emoji", None, f"emoji 另有 {len(emoji_hits) - 20} 处未逐条列出")
            )
    for lineno, term, kind in banned_hits:
        report.violations.append(Violation(kind, lineno, f"{kind}第 {lineno} 行：{term}"))
    if report.meme_count > rules.meme_max:
        shown = "、".join(f"{term}（第 {lineno} 行）" for lineno, term in meme_hits[:8])
        report.violations.append(
            Violation(
                "meme",
                meme_hits[0][0] if meme_hits else None,
                f"热梗 {report.meme_count} 处，上限 {rules.meme_max}：{shown}",
            )
        )

    report.violations.sort(key=lambda item: (item.line is None, item.line or 0, item.kind))
    return report


def format_report(report: Report) -> str:
    rules = report.rules
    chain = "有" if report.chain_hit else "无"
    lines = [
        "真人写作风格检查",
        f"- 文件：{show_path(report.path)}",
        f"- 规则：{show_path(report.rules_path)}",
        "- 允许的口语：" + "、".join(rules.colloquial_allowed),
        "- 热梗上限：{}（{}）".format(rules.meme_max, "、".join(rules.memes)),
        "- 人工不判：自嘲 1–2 处；标题用亲历型，或问句/反差钩子；每个数字都要有场景；不规定篇长",
        "",
        "计数",
        f"- 正文段：{report.prose_paragraphs}",
        f"- 加粗：{report.bold_count} / {rules.bold_max}",
        f"- emoji：{report.emoji_count} / {rules.emoji_max}",
        f"- 热梗：{report.meme_count} / {rules.meme_max}",
        f"- 超长段：{report.long_paragraphs}",
        f"- 禁用词：{report.banned_hits}",
        f"- 连接词链：{chain}",
        f"- 层层叠加：{report.stacking_hits}",
        "",
    ]
    if not report.violations:
        lines.append("违规")
        lines.append("- 无")
        lines.append("")
        lines.append("结果：通过")
        return "\n".join(lines) + "\n"
    lines.append(f"违规（{len(report.violations)}）")
    for index, item in enumerate(report.violations, start=1):
        lines.append(f"{index}. {item.message}")
    lines.append("")
    lines.append(f"结果：未通过（{len(report.violations)} 条）")
    return "\n".join(lines) + "\n"


def self_test(rules: Rules) -> None:
    def check(name: str, text: str, pred) -> None:
        report = lint_text(text, rules, path=name)
        if not pred(report):
            raise SystemExit(f"自检失败：{name}\n{format_report(report)}")

    clean = "---\ntitle: t\n---\n\n# 记一次短文\n\n上周我接手一台老机器，日志每分钟打满。\n\n好家伙，十分钟就满了。\n\n没有比日志更好的老师了。\n"
    check("clean", clean, lambda report: not report.violations)

    check(
        "banned",
        "综上所述，问题已经解决。\n",
        lambda report: any(item.kind == "禁用词" for item in report.violations),
    )
    check(
        "emoji",
        "跑完了 ✅\n",
        lambda report: any(item.kind == "emoji" for item in report.violations),
    )
    bold = "\n".join(f"第 {i} 点是 **词{i}** 本身。" for i in range(1, 7)) + "\n"
    check(
        "bold",
        bold,
        lambda report: any(item.kind == "bold" for item in report.violations),
    )
    check(
        "label",
        "- **消除竞态条件**：把锁拿掉。\n",
        lambda report: any(item.kind == "bold_label" for item in report.violations),
    )
    check(
        "chain",
        "首先看日志。其次看监控。最后才改代码。\n",
        lambda report: report.chain_hit,
    )
    check(
        "last-alone",
        "最后一步留给人。\n",
        lambda report: not report.chain_hit and not any(item.kind == "禁用词" for item in report.violations),
    )
    check(
        "stack-full",
        "它不仅更快，而且更稳，更省机器。\n",
        lambda report: report.stacking_hits >= 1,
    )
    check(
        "stack-once",
        "它不仅更快，而且更稳。\n",
        lambda report: report.stacking_hits == 0,
    )
    check(
        "meme",
        "好家伙，第一次。\n\n好家伙，第二次。\n",
        lambda report: any(item.kind == "meme" for item in report.violations),
    )
    check(
        "meme-once",
        "好家伙，只有一次。\n",
        lambda report: not any(item.kind == "meme" for item in report.violations),
    )
    long = "汉" * 121 + "。\n"
    check(
        "paragraph",
        long,
        lambda report: any(item.kind == "paragraph" for item in report.violations),
    )
    check(
        "ending",
        "第一句就很长，已经超过一行能读完的程度，所以不该拿来收尾。第二句还在总结。\n",
        lambda report: any(item.kind == "ending" for item in report.violations),
    )
    fenced = "正文很短。\n\n```\n综上所述 ✅ **甲** **乙** **丙** **丁** **戊** **己**\n首先其次最后\n```\n\n一次通过。\n"
    check("fence", fenced, lambda report: not report.violations)
    check(
        "yyds",
        "这个方案 YYDS。\n",
        lambda report: any(item.kind == "口语" for item in report.violations),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按真人写作风格规则检查一篇 Markdown")
    parser.add_argument("markdown", nargs="?", help="要检查的 Markdown 文件")
    parser.add_argument("--rules", default=str(DEFAULT_RULES), help="style-rules.md 的路径")
    parser.add_argument("--self-test", action="store_true", help="用内置样例检查规则是否生效")
    args = parser.parse_args(argv)

    try:
        rules = parse_rules(Path(args.rules))
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2

    if args.self_test:
        self_test(rules)
        print("自检通过")
        return 0

    if not args.markdown:
        parser.print_help(sys.stderr)
        return 2

    target = Path(args.markdown)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"读不到文章：{target}（{exc}）", file=sys.stderr)
        return 2

    report = lint_text(text, rules, path=str(target))
    sys.stdout.write(format_report(report))
    return 1 if report.violations else 0


if __name__ == "__main__":
    sys.exit(main())
