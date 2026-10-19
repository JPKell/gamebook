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

ROLES = (
    "writer",
    "critic",
    "editor",
    "summarizer",
    "consistency",
    "suggester",
    "lore_extractor",
    "player",
)

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

CONSISTENCY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["warning", "info"]},
                    "kind": {
                        "type": "string",
                        "enum": ["path_validity", "lore", "continuity", "mechanics", "other"],
                    },
                    "quote": {"type": "string"},
                    "problem": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["problem"],
            },
        }
    },
    "required": ["issues"],
}

SUGGESTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string"},
                    "title": {"type": "string"},
                    "beat_notes": {"type": "string"},
                    "beat": {"type": "string"},
                },
                "required": ["ref", "title"],
            },
        },
        "choices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["from", "to"],
            },
        },
    },
    "required": ["nodes", "choices"],
}

LORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "existing_key": {"type": ["string", "null"]},
                    "role": {"type": "string"},
                    "appearance": {"type": "string"},
                    "voice": {"type": "string"},
                    "motivations": {"type": "string"},
                    "notes": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "existing_key": {"type": ["string", "null"]},
                    "type": {
                        "type": "string",
                        "enum": ["location", "faction", "history", "glossary", "other"],
                    },
                    "body": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    "required": ["characters", "entries"],
}

DEFAULTS["consistency"] = (
    "You check one section of an interactive gamebook for consistency. Report only real "
    "problems: the prose assumes something only some readers have (path_validity), "
    "contradicts the lore or characters (lore), contradicts the section before it "
    "(continuity), or contradicts the game mechanics, e.g. mentions an item or enemy that "
    "isn't there (mechanics). Quote the exact words. If there's nothing wrong, return no "
    'issues. Respond with JSON only: {"issues": [{"severity": "warning"|"info", "kind", '
    '"quote", "problem", "suggestion"}]}.',
    _CONTEXT
    + """
<may>{{ ctx.digest.may_text }}</may>
<prose>
{{ prose }}
</prose>""",
)

DEFAULTS["suggester"] = (
    "You help plan an interactive gamebook. From the act outline and the sections that "
    "already exist, propose new sections and choices that cover the story beats with no "
    "sections yet, and fill dead ends. Keep it small: at most five new sections. Refer to "
    "existing sections by their key and to new ones by a ref like new1. Respond with JSON "
    'only: {"rationale", "nodes": [{"ref", "title", "beat_notes", "beat"}], '
    '"choices": [{"from", "to", "label"}]}.',
    """BOOK: {{ book.title }}
ACT: {{ act.title }}{% if act.summary %} — {{ act.summary }}{% endif %}
STORY BEATS
{% for b in beats %}- {{ b.title }}{% if b.description %}: {{ b.description }}{% endif %}{% if b.nodes %} (told in: {{ b.nodes | join(", ") }}){% else %} (NO SECTIONS YET){% endif %}
{% endfor %}<unlinked_beats>
{% for b in beats if not b.nodes %}{{ b.title }}|{{ b.description }}
{% endfor %}</unlinked_beats>
EXISTING SECTIONS (key | title | notes | choices)
<nodes>
{% for n in nodes %}{{ n.key }}|{{ n.title }}|{{ n.flags }}|{{ n.beat_notes }}|{% for c in n.choices %}{{ c.label }} -> {{ c.to }}; {% endfor %}
{% endfor %}</nodes>
{% if notes %}AUTHOR'S NOTES: {{ notes }}
{% endif %}Propose the new sections and choices now.""",
)

DEFAULTS["lore_extractor"] = (
    "You maintain the lore wiki of a gamebook series. From the approved prose below, list "
    "characters and places, factions, history or terms that the wiki doesn't have yet, or "
    "new facts about ones it has (give existing_key for those). Only include what the prose "
    "states; quote it as evidence. Respond with JSON only: "
    '{"characters": [{"name", "existing_key", "role", "appearance", "voice", "motivations", '
    '"notes", "evidence"}], "entries": [{"name", "existing_key", "type", "body", "evidence"}]}.',
    """THE WIKI ALREADY HAS
<existing>
{% for e in existing %}{{ e.kind }}|{{ e.key }}|{{ e.name }}
{% endfor %}</existing>
APPROVED PROSE
{% for p in prose %}<section title="{{ p.title }}">
{{ p.text }}
</section>
{% endfor %}""",
)

PLAYER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "choice": {"type": "integer", "minimum": 1},
        "reasoning": {"type": "string"},
        "memory": {"type": "string"},
        "confused": {"type": "boolean"},
        "confusion": {"type": "string"},
    },
    "required": ["choice", "reasoning", "memory"],
}

#: How each persona plays (the player's system prompt includes one).
PERSONAS: dict[str, str] = {
    "cautious": "You play carefully: you avoid fights and gambles when there's another way, "
    "keep your health up, and value survival over treasure.",
    "reckless": "You play boldly: you take fights, gambles and risky shortcuts, and you "
    "rarely back down.",
    "completionist": "You want to see everything: you pick up every item, explore side paths "
    "and try options you haven't tried before.",
    "role-player": "You play as the hero of the story: you choose what the character would "
    "most plausibly do given the story so far, not what is mechanically best.",
}

DEFAULTS["player"] = (
    "You are playing an interactive gamebook as a reader, one section at a time. You see "
    "only what a reader sees. {{ persona }} Pick one of the numbered options. If the text is "
    "confusing, contradicts itself, or doesn't explain your options, say so in "
    '"confusion" and set "confused" to true; otherwise leave it empty. Keep "memory" as a '
    "short running summary (under 80 words) of your adventure so far and what you want to "
    "do next. Respond with JSON only: "
    '{"choice": <number>, "reasoning": "...", "memory": "...", "confused": false, '
    '"confusion": ""}.',
    """{% if memory %}YOUR NOTES SO FAR
{{ memory }}

{% endif %}<page>
{{ page }}
</page>
<options>
{% for o in options %}{{ loop.index }}. {{ o }}
{% endfor %}</options>
Choose a number from 1 to {{ options | length }}.""",
)

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
