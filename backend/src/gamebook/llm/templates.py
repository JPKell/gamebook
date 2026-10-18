"""Prompt templates: built-in defaults per role and a sandboxed Jinja2 renderer.

Templates receive ``ctx`` (the assembled node context, see
``services/writing_context.py``) plus role extras: ``draft``, ``issues``,
``notes`` and ``text``. Rendering is strict: an unknown variable is an error,
so a typo in an edited template fails loudly instead of silently dropping context.
"""

from __future__ import annotations

from typing import Any

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

ROLES = ("writer", "critic", "editor", "summarizer")

RUBRIC = (
    "beat_adherence",
    "continuity",
    "path_validity",
    "style",
    "choice_setup",
    "prose_quality",
)

#: JSON schema for the critic's report (sent as response_format when supported).
CRITIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": {k: {"type": "number", "minimum": 0, "maximum": 10} for k in RUBRIC},
            "required": list(RUBRIC),
        },
        "overall": {"type": "number", "minimum": 0, "maximum": 10},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "problem": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["problem"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["scores", "overall", "issues"],
}

_CONTEXT = """\
{%- if ctx.style %}
STYLE GUIDE
Point of view: {{ ctx.style.pov }}. Tense: {{ ctx.style.tense }}. Length: {{ ctx.style.word_min }} to {{ ctx.style.word_max }} words.
{% if ctx.style.voice %}Voice: {{ ctx.style.voice }}
{% endif %}{% if ctx.style.notes %}Notes: {{ ctx.style.notes }}
{% endif %}{% endif %}
BOOK: {{ ctx.book.title }}
ACT: {{ ctx.act.title }}{% if ctx.act.summary %} — {{ ctx.act.summary }}{% endif %}
{% for b in ctx.beats %}Story beat: {{ b.title }}{% if b.description %} — {{ b.description }}{% endif %}
{% endfor %}
{%- if ctx.story_so_far %}
STORY SO FAR (one route the reader may have taken)
{% for s in ctx.story_so_far %}- {{ s }}
{% endfor %}{% endif %}
{%- if ctx.previous_text %}
THE SECTION JUST BEFORE ({{ ctx.previous_title }})
<previous>
{{ ctx.previous_text }}
</previous>
{% endif %}
WHAT EVERY READER HERE HAS: {{ ctx.digest.must_text or "nothing in particular" }}
WHAT ONLY SOME READERS HAVE (never assume these): {{ ctx.digest.may_text or "nothing" }}
{% if ctx.location %}
LOCATION: {{ ctx.location.name }}
{{ ctx.location.text }}
{% endif %}
{%- for c in ctx.characters %}
CHARACTER: {{ c.name }}{% if c.role %} ({{ c.role }}){% endif %}
{% for line in c.lines %}{{ line }}
{% endfor %}{% endfor %}
{%- for m in ctx.mentioned %}
ALSO MENTIONED: {{ m.name }} — {{ m.text }}
{% endfor %}
SECTION: {{ ctx.node.title }}{% if ctx.variant.condition %} (this version is shown when {{ ctx.variant.condition }}){% endif %}
{%- if ctx.node.ending %}
This section is an ending ({{ ctx.node.ending }}).{% endif %}
{%- if ctx.encounters %}
Encounters here (names only; mechanics are printed separately): {{ ctx.encounters | join(", ") }}{% endif %}
{%- if ctx.items_here %}
Items here: {{ ctx.items_here | join(", ") }}{% endif %}
<beat_notes>
{{ ctx.node.beat_notes or "(no beat notes)" }}
</beat_notes>
<choices>
{% for c in ctx.choices %}- {{ c }}
{% endfor %}</choices>
"""

DEFAULTS: dict[str, tuple[str, str]] = {
    "writer": (
        "You are the writer of an interactive gamebook. Write the prose for one numbered "
        "section. Second person unless the style guide says otherwise. Follow the beat notes "
        "and the style guide exactly. Never state numbers, dice or game mechanics, and never "
        "write the choices themselves: end so that the listed choices follow naturally. "
        "Never assume anything listed under 'only some readers have'. Output only the prose.",
        _CONTEXT
        + """
{% if notes %}AUTHOR'S NOTES FOR THIS DRAFT: {{ notes }}
{% endif %}Write the section now.""",
    ),
    "critic": (
        "You are a demanding gamebook editor. Score the draft from 0 to 10 on each rubric "
        "item: beat_adherence (follows the beat notes), continuity (consistent with the story "
        "so far, lore and characters), path_validity (assumes nothing only some readers "
        "have), style (follows the style guide), choice_setup (the ending sets up every "
        "choice), prose_quality. Give 'overall' and concrete issues, quoting the draft. "
        'Respond with JSON only: {"scores": {...}, "overall": n, "issues": [{"quote", '
        '"problem", "suggestion"}], "summary": "..."}.',
        _CONTEXT
        + """
<draft>
{{ draft }}
</draft>""",
    ),
    "editor": (
        "You are the editor. Rewrite the draft to fix every issue listed, keeping what works. "
        "Keep the style guide and never assume anything only some readers have. Output only "
        "the revised prose.",
        _CONTEXT
        + """
<draft>
{{ draft }}
</draft>
ISSUES TO FIX:
{% for i in issues %}- {% if i.quote %}"{{ i.quote }}": {% endif %}{{ i.problem }}{% if i.suggestion %} → {{ i.suggestion }}{% endif %}
{% endfor %}
{% if notes %}AUTHOR'S NOTES: {{ notes }}
{% endif %}Rewrite the section now.""",
    ),
    "summarizer": (
        "Summarise this gamebook section in two or three plain sentences, in the past tense, "
        "for continuity notes: what happened and anything the reader learned or gained. "
        "Output only the summary.",
        """SECTION: {{ ctx.node.title }}
<text>
{{ text }}
</text>""",
    ),
}

_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)


def render(source: str, **variables: Any) -> str:
    """Render a template; raises ``TemplateError`` (with a readable message) on mistakes."""
    return _env.from_string(source).render(**variables).strip()


def check(source: str) -> str | None:
    """Syntax check for the editor: None if it parses, else the error."""
    try:
        _env.parse(source)
    except TemplateError as exc:
        return str(exc)
    return None
