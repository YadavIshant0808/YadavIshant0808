#!/usr/bin/env python3
"""
generate_terminal.py

Generates assets/terminal.svg — an animated, typing-effect terminal hero
for the GitHub profile README. Pure SVG + SMIL animation: no JavaScript,
no external services, no paid tooling. Renders correctly on GitHub's
camo-proxied img rendering.

Usage:
    python3 scripts/generate_terminal.py

Reads:  config/profile.json
Writes: assets/terminal.svg

Design notes:
- Every line is typed out character-by-character using stacked <tspan>
  reveal animations (opacity keyframes timed against character count),
  which is the one typing-animation technique that survives GitHub's
  SVG sanitizer (it strips <script>, most CSS animation shorthand edge
  cases, and anything JS-triggered, but preserves <animate>/SMIL).
- A separate blinking-cursor rect runs on an infinite loop, independent
  of the typing sequence, so it keeps blinking after typing finishes.
- All dynamic text is XML-escaped via xml.sax.saxutils.escape.
- Layout is a fixed-height, percentage-friendly viewBox so it scales
  down cleanly on mobile widths.
"""

import json
import os
import sys
from xml.sax.saxutils import escape

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "profile.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "assets", "terminal.svg")

# --- layout constants -------------------------------------------------
FONT_SIZE = 15
LINE_HEIGHT = 24
CHAR_WIDTH = 9.1          # approximate advance width for the mono font at 15px
PADDING_X = 24
PADDING_TOP = 52          # space reserved for the fake window chrome bar
PADDING_BOTTOM = 24
CHROME_HEIGHT = 36
WIDTH = 760
TYPE_SPEED = 0.045        # seconds per character
LINE_GAP_AFTER_CMD = 0.35 # pause after a command line finishes typing
LINE_GAP_AFTER_BLOCK = 0.6
CURSOR_BLINK_PERIOD = 1.0


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def esc(s: str) -> str:
    return escape(s, {'"': "&quot;", "'": "&apos;"})


def build_typed_line(text, x, y, start_time, css_class, extra_id):
    """
    Returns (svg_fragment, end_time) for one line of text that types
    itself out character by character using per-character <tspan>
    opacity keyframes driven by <animate>. This avoids relying on
    CSS @keyframes-in-<style> support and works reliably through
    GitHub's SVG sanitizer.
    """
    if text == "":
        # blank line — just advances time slightly, no visible content
        return "", start_time + 0.1

    n = len(text)
    duration = n * TYPE_SPEED
    # Build one <text> element containing per-char <tspan>s, each with
    # its own opacity <animate> that flips 0 -> 1 at its scheduled time.
    tspans = []
    for i, ch in enumerate(text):
        char_start = start_time + i * TYPE_SPEED
        display_ch = ch if ch != " " else "\u00a0"  # nbsp so spacing survives
        tspans.append(
            '<tspan id="{eid}-c{i}" opacity="0">{ch}'
            '<animate attributeName="opacity" from="0" to="1" '
            'begin="{begin:.3f}s" dur="0.01s" fill="freeze" /></tspan>'.format(
                eid=extra_id, i=i, ch=esc(display_ch), begin=char_start
            )
        )

    frag = '<text x="{x}" y="{y}" class="{cls}">{spans}</text>'.format(
        x=x, y=y, cls=css_class, spans="".join(tspans)
    )
    return frag, start_time + duration


def build_cursor(x, y, blink_start):
    """A blinking block cursor that starts blinking once typing reaches it,
    and loops forever after."""
    return (
        '<rect x="{x}" y="{y}" width="8" height="16" class="cursor">'
        '<animate attributeName="opacity" '
        'values="1;1;0;0;1" keyTimes="0;0.01;0.5;0.99;1" '
        'dur="{period}s" begin="{begin:.3f}s" repeatCount="indefinite" />'
        "</rect>"
    ).format(x=x, y=y, period=CURSOR_BLINK_PERIOD, begin=blink_start)


def generate(config):
    prompt = config["terminal"]["prompt"]
    commands = config["terminal"]["commands"]
    theme = config["theme"]

    lines_svg = []
    t = 0.6  # small initial delay before typing starts
    cur_y = PADDING_TOP + LINE_HEIGHT
    line_index = 0
    final_cursor_x = PADDING_X
    final_cursor_y = cur_y - 12

    for block in commands:
        cmd_text = "{} {}".format(prompt, block["cmd"])
        frag, t = build_typed_line(
            cmd_text, PADDING_X, cur_y, t, "line prompt-line", "l{}".format(line_index)
        )
        lines_svg.append(frag)
        final_cursor_x = PADDING_X + len(cmd_text) * CHAR_WIDTH
        final_cursor_y = cur_y - 12
        cur_y += LINE_HEIGHT
        line_index += 1
        t += LINE_GAP_AFTER_CMD

        for out_line in block["output"]:
            frag, t = build_typed_line(
                out_line, PADDING_X, cur_y, t, "line output-line", "l{}".format(line_index)
            )
            lines_svg.append(frag)
            final_cursor_x = PADDING_X + len(out_line) * CHAR_WIDTH
            final_cursor_y = cur_y - 12
            cur_y += LINE_HEIGHT
            line_index += 1

        t += LINE_GAP_AFTER_BLOCK

    total_content_height = cur_y + PADDING_BOTTOM
    height = max(total_content_height, 260)

    cursor_svg = build_cursor(final_cursor_x + 4, final_cursor_y, t)

    svg = """<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" \
xmlns="http://www.w3.org/2000/svg" role="img" \
aria-label="Animated terminal showing Ishant Yadav's role and current focus">
  <title>Ishant Yadav — AI &amp; Backend Developer terminal</title>
  <defs>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{bg_alt}" />
      <stop offset="100%" stop-color="{bg}" />
    </linearGradient>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.2" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <style>
      .chrome {{ fill: {bg_alt}; }}
      .chrome-border {{ stroke: {border}; stroke-width: 1; fill: none; }}
      .dot {{ opacity: 0.85; }}
      .titlebar-text {{
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 12px;
        fill: {text_muted};
      }}
      .line {{
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: {font_size}px;
        white-space: pre;
      }}
      .prompt-line {{ fill: {crimson_glow}; filter: url(#glow); }}
      .output-line {{ fill: {text_primary}; }}
      .cursor {{ fill: {crimson_glow}; filter: url(#glow); }}
    </style>
  </defs>

  <rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="url(#bgGrad)" />
  <rect x="0.5" y="0.5" width="{width_minus1}" height="{height_minus1}" rx="10" class="chrome-border" />

  <rect x="0" y="0" width="{width}" height="{chrome_height}" rx="10" class="chrome" />
  <rect x="0" y="{chrome_height_half}" width="{width}" height="{chrome_height_half}" class="chrome" />
  <line x1="0" y1="{chrome_height}" x2="{width}" y2="{chrome_height}" class="chrome-border" />

  <circle cx="24" cy="18" r="6" class="dot" fill="#ff5f56" />
  <circle cx="44" cy="18" r="6" class="dot" fill="#ffbd2e" />
  <circle cx="64" cy="18" r="6" class="dot" fill="#27c93f" />
  <text x="{width_half}" y="22" text-anchor="middle" class="titlebar-text">ishant@github: ~</text>

  {lines}
  {cursor}
</svg>
""".format(
        width=WIDTH,
        width_minus1=WIDTH - 1,
        height=height,
        height_minus1=height - 1,
        width_half=WIDTH // 2,
        bg=theme["bg"],
        bg_alt=theme["bg_alt"],
        border=theme["border"],
        crimson_glow=theme["crimson_glow"],
        text_primary=theme["text_primary"],
        text_muted=theme["text_muted"],
        font_size=FONT_SIZE,
        chrome_height=CHROME_HEIGHT,
        chrome_height_half=CHROME_HEIGHT / 2,
        lines="\n  ".join(lines_svg),
        cursor=cursor_svg,
    )

    return svg


def main():
    if not os.path.isfile(CONFIG_PATH):
        print("ERROR: config file not found at {}".format(CONFIG_PATH), file=sys.stderr)
        sys.exit(1)

    config = load_config()
    svg = generate(config)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print("Wrote {} ({} bytes)".format(OUTPUT_PATH, len(svg.encode("utf-8"))))


if __name__ == "__main__":
    main()
