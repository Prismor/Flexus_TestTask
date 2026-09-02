# -*- coding: utf-8 -*-
#  Shared by build_clean_shaders.py and build_shadertoy.py: parses
#  LiquidSimCore.ush into one block per struct/function, and resolves the
#  call graph so a generator can pull in exactly what one effect needs and
#  nothing else.

import re

_START_RE = re.compile(r"^(?:struct\s+(LS_\w+)|[\w0-9_]+\s+(LS_\w+)\s*\()")


def parse_blocks(text):
    """Return {symbol: source} for every struct and function in the core,
    keeping the comment block that sits directly above each one."""
    lines = text.splitlines()
    blocks = {}

    i = 0
    while i < len(lines):
        m = _START_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1) or m.group(2)

        top = i
        while top > 0:
            prev = lines[top - 1].strip()
            if prev.startswith("//") or (prev == "" and top - 2 >= 0 and lines[top - 2].strip().startswith("//")):
                top -= 1
            else:
                break
        while top < i and lines[top].strip() == "":
            top += 1

        depth = 0
        started = False
        j = i
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            if "{" in lines[j]:
                started = True
            if started and depth <= 0:
                break
            j += 1

        blocks[name] = strip_section_banner(lines[top:j + 1])
        i = j + 1

    return blocks


def strip_section_banner(block_lines):
    """Drop the core's own "==== 7. SHADING MODELS ====" dividers: they refer
    to the layout of the core file and mean nothing in a per-effect file."""
    out = []
    in_banner = False
    for line in block_lines:
        stripped = line.strip()
        if stripped.startswith("// ====") and stripped.endswith("===="):
            in_banner = not in_banner
            continue
        if in_banner:
            continue
        out.append(line)
    while out and out[0].strip() == "":
        out.pop(0)
    return "\n".join(out)


def resolve(symbols, blocks):
    """Follow the call graph so a file gets every helper it needs, in the
    order they are defined in the core (definitions must precede use).

    A bare word match is not enough: a dev-note comment can *name* a
    function without calling it (e.g. "the original passed viewDir to
    LS_Iridescent" - a note about a rejected approach, not a call), and that
    would wrongly pull the whole function in. A struct name is never
    "called" though - it only ever appears as a bare type, so it has to
    stay a bare-word match."""
    needed = set()
    queue = list(symbols)
    while queue:
        s = queue.pop()
        if s in needed or s not in blocks:
            continue
        needed.add(s)
        body = blocks[s]
        for ref in set(re.findall(r"\b(LS_\w+)\b", body)):
            if ref == s or ref not in blocks or ref in needed:
                continue
            is_struct = blocks[ref].lstrip().startswith("struct")
            is_real_call = re.search(r"\b" + re.escape(ref) + r"\s*\(", body)
            if is_struct or is_real_call:
                queue.append(ref)
    return [s for s in blocks if s in needed]   # dict preserves core order


def pruned_core(core_text, entry_symbols):
    """The subset of the core that entry_symbols actually need, joined back
    into one text block in core order."""
    blocks = parse_blocks(core_text)
    order = resolve(entry_symbols, blocks)
    return "\n\n".join(blocks[s] for s in order)


def strip_comment_blocks(text, min_block_lines=3):
    """Remove standalone comment paragraphs - min_block_lines or more
    consecutive full-line "//" comments, the verbose development-rationale
    prose that belongs in LiquidSimCore.ush but not in a client-facing
    export. A single isolated comment line survives as a short label, and a
    trailing "// Name" comment on a code line is untouched either way."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("//"):
            j = i
            while j < len(lines) and lines[j].strip().startswith("//"):
                j += 1
            if j - i >= min_block_lines:
                i = j
                continue
        out.append(lines[i])
        i += 1

    collapsed = []
    blank = False
    for line in out:
        if line.strip() == "":
            if blank:
                continue
            blank = True
        else:
            blank = False
        collapsed.append(line)
    while collapsed and collapsed[0].strip() == "":
        collapsed.pop(0)
    return "\n".join(collapsed)
