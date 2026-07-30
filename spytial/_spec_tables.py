"""Field tables and value vocabularies for the spytial layout-spec language.

GENERATED FILE -- DO NOT EDIT BY HAND.

    Source:   spytial/_vendor/spytial-language.json
    Language: 2026-07-29 (spytial-core 4.3.0)
    Regenerate with: python3 scripts/generate_spec_tables.py

Everything here is derived from the manifest spytial-core publishes, so a
field, section, or vocabulary that changes upstream changes here as a diff
in review rather than as a spec that quietly stops matching. Deliberate
differences from the manifest are declared in the generator's override
tables, each with its reason.
"""

# The manifest this was generated from. `LANGUAGE_VERSION` only moves when
# the spec language itself changes, so an unchanged value across a
# spytial-core bump means nothing here needed revisiting.
LANGUAGE_VERSION = '2026-07-29'
CORE_VERSION = '4.3.0'


# --------------------------------------------------------------------------- #
# Value vocabularies
# --------------------------------------------------------------------------- #
#
# These are TypeScript union types in core, so they are erased at runtime and
# nothing downstream re-checks them. An unrecognized value is kept by the
# parser and then quietly does the wrong thing -- an out-of-vocab orientation
# direction matches no case and the constraint evaporates; a misspelled cyclic
# direction reads as 'clockwise'; an unknown flag name does nothing. Authoring
# time is the only place they can surface.

ALIGN_DIRECTIONS = (
    'horizontal',
    'vertical',
)

CONSTRAINT_HOLDS = (
    'always',
    'never',
)

FLAG_NAMES = (
    'hideDisconnected',
    'hideDisconnectedBuiltIns',
)

GROUP_EDGE_DIRECTIONS = (
    'none',
    'togroup',
    'fromgroup',
)

ICON_PLACEMENTS = (
    'full',
    'badge',
)

LINE_PATTERNS = (
    'solid',
    'dashed',
    'dotted',
)

ORIENTATION_DIRECTIONS = (
    'above',
    'below',
    'left',
    'right',
    'directlyAbove',
    'directlyBelow',
    'directlyLeft',
    'directlyRight',
)

ROTATION_DIRECTIONS = (
    'clockwise',
    'counterclockwise',
)

TEXT_SIZES = (
    'small',
    'normal',
    'large',
)


# --------------------------------------------------------------------------- #
# Field tables
# --------------------------------------------------------------------------- #
#
# `hold` is optional on every constraint that supports negation: core reads
# `hold: never` off the inner block and flips the constraint to its negation.
# A key with a list of field sets accepts any one of them (`group`, whose
# deprecated by-field form takes different keys than the selector form).

CONSTRAINT_TYPES = {
    'orientation': {
        'required': [
            'selector',
            'directions',
        ],
        'optional': [
            'hold',
        ],
    },
    'cyclic': {
        'required': [
            'selector',
            'direction',
        ],
        'optional': [
            'hold',
        ],
    },
    'align': {
        'required': [
            'selector',
            'direction',
        ],
        'optional': [
            'hold',
        ],
    },
    'group': [
        {
            'required': [
                'selector',
                'name',
            ],
            'optional': [
                'addEdge',
                'textStyle',
                'hold',
            ],
        },
        {
            'required': [
                'field',
                'groupOn',
                'addToGroup',
            ],
            'optional': [
                'selector',
                'hold',
            ],
        },
    ],
    'size': {
        'required': [
            'width',
            'height',
        ],
        'optional': [
            'selector',
        ],
    },
    'hideAtom': {
        'required': [
            'selector',
        ],
        'optional': [],
    },
}

DIRECTIVE_TYPES = {
    'flag': {
        'required': [
            'name',
        ],
        'optional': [],
    },
    'atomStyle': {
        'required': [],
        'optional': [
            'selector',
            'fillStyle',
            'borderStyle',
            'iconStyle',
            'textStyle',
            'showLabel',
        ],
    },
    'edgeStyle': {
        'required': [
            'field',
        ],
        'optional': [
            'selector',
            'filter',
            'lineStyle',
            'textStyle',
            'showLabel',
            'hidden',
        ],
    },
    'attribute': {
        'required': [
            'field',
        ],
        'optional': [
            'selector',
            'filter',
            'textStyle',
        ],
    },
    'tag': {
        'required': [
            'toTag',
            'name',
            'value',
        ],
        'optional': [
            'textStyle',
        ],
    },
    'hideField': {
        'required': [
            'field',
        ],
        'optional': [
            'selector',
            'filter',
        ],
    },
    'inferredEdge': {
        'required': [
            'name',
            'selector',
        ],
        'optional': [
            'draw',
            'lineStyle',
            'textStyle',
            'color',
            'style',
            'weight',
            'highlight',
        ],
    },
    'icon': {
        'required': [
            'selector',
            'path',
            'showLabels',
        ],
        'optional': [],
    },
    'atomColor': {
        'required': [
            'value',
            'selector',
        ],
        'optional': [],
    },
    'edgeColor': {
        'required': [
            'field',
            'value',
        ],
        'optional': [
            'selector',
            'filter',
            'style',
            'weight',
            'highlight',
            'showLabel',
            'hidden',
        ],
    },
    'projection': {
        'required': [
            'sig',
        ],
        'optional': [],
    },
}

# Items written as a bare scalar rather than a mapping
# (`- flag: hideDisconnected`), mapped to the keyword carrying the value.
SCALAR_ITEMS = {
    'flag': 'name',
}


# --------------------------------------------------------------------------- #
# Author-time value checking
# --------------------------------------------------------------------------- #

# (annotation type, keyword) -> the values core accepts. List-valued keywords
# are checked element-wise.
ENUM_VALUES = {
    ('align', 'direction'): ALIGN_DIRECTIONS,
    ('cyclic', 'direction'): ROTATION_DIRECTIONS,
    ('flag', 'name'): FLAG_NAMES,
    ('orientation', 'directions'): ORIENTATION_DIRECTIONS,
}


# --------------------------------------------------------------------------- #
# Shared style blocks
# --------------------------------------------------------------------------- #
#
# The dataclasses in annotations.py are hand-written -- they carry the
# docstrings and real signatures that `help()` shows -- and test_spec_tables.py
# holds them to the shape below.

BLOCKS = {
    'textStyle': {
        'size': {
            'type': 'enum',
            'enum': 'TEXT_SIZES',
        },
        'color': {
            'type': 'color',
        },
    },
    'lineStyle': {
        'color': {
            'type': 'color',
        },
        'pattern': {
            'type': 'enum',
            'enum': 'LINE_PATTERNS',
        },
        'weight': {
            'type': 'number',
            'exclusiveMinimum': 0,
        },
        'highlight': {
            'type': 'color',
        },
    },
    'fillStyle': {
        'color': {
            'type': 'color',
        },
    },
    'borderStyle': {
        'color': {
            'type': 'color',
        },
        'width': {
            'type': 'number',
            'exclusiveMinimum': 0,
        },
    },
    'iconStyle': {
        'path': {
            'type': 'icon-path',
        },
        'placement': {
            'type': 'enum',
            'enum': 'ICON_PLACEMENTS',
        },
        'opacity': {
            'type': 'number',
            'minimum': 0,
            'maximum': 1,
        },
    },
}


# --------------------------------------------------------------------------- #
# Deprecations
# --------------------------------------------------------------------------- #
#
# A deprecated form keeps parsing and keeps its meaning until a spytial-core
# major. `mapping` is the rewrite core documents; annotations.py implements it
# in _desugar_legacy_style so the emitted spec uses the current spelling.

DEPRECATED_ITEMS = {
    'group.byField': {
        'path': 'group',
        'replacedBy': 'group',
        'mapping': {
            'field': 'selector',
            'groupOn': 'selector (column order)',
            'addToGroup': 'selector (column order)',
            'selector': 'selector',
        },
    },
    'icon': {
        'path': 'icon',
        'replacedBy': 'atomStyle',
        'mapping': {
            'path': 'iconStyle.path',
            'selector': 'selector',
            'showLabels: false': 'showLabel: false + iconStyle.placement: full',
            'showLabels: true': 'showLabel: true + iconStyle.placement: badge',
        },
    },
    'atomColor': {
        'path': 'atomColor',
        'replacedBy': 'atomStyle',
        'mapping': {
            'value': 'borderStyle.color',
            'selector': 'selector',
        },
    },
    'edgeColor': {
        'path': 'edgeColor',
        'replacedBy': 'edgeStyle',
        'mapping': {
            'value': 'lineStyle.color',
            'style': 'lineStyle.pattern',
            'weight': 'lineStyle.weight',
            'highlight': 'lineStyle.highlight',
            'field': 'field',
            'selector': 'selector',
            'filter': 'filter',
            'showLabel': 'showLabel',
            'hidden': 'hidden',
        },
    },
}

DEPRECATED_FIELDS = {
    'inferredEdge.color': {
        'path': 'inferredEdge.color',
        'replacedBy': 'inferredEdge.lineStyle.color',
        'mapping': {
            'color': 'lineStyle.color',
        },
    },
    'inferredEdge.style': {
        'path': 'inferredEdge.style',
        'replacedBy': 'inferredEdge.lineStyle.pattern',
        'mapping': {
            'style': 'lineStyle.pattern',
        },
    },
    'inferredEdge.weight': {
        'path': 'inferredEdge.weight',
        'replacedBy': 'inferredEdge.lineStyle.weight',
        'mapping': {
            'weight': 'lineStyle.weight',
        },
    },
    'inferredEdge.highlight': {
        'path': 'inferredEdge.highlight',
        'replacedBy': 'inferredEdge.lineStyle.highlight',
        'mapping': {
            'highlight': 'lineStyle.highlight',
        },
    },
}
