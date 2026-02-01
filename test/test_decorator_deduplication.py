#!/usr/bin/env python3
"""
Tests to ensure decorator deduplication reduces redundant YAML rules.
"""

from spytial.annotations import (
    annotate_orientation,
    collect_decorators,
    serialize_to_yaml_string,
    orientation,
    atomColor,
)


def test_duplicate_object_annotations_are_deduplicated():
    """Applying the same annotation twice to an object should result in a single entry."""
    my_list = [1, 2, 3]
    annotate_orientation(my_list, selector='items', directions=['horizontal'])
    annotate_orientation(my_list, selector='items', directions=['horizontal'])

    decorators = collect_decorators(my_list)
    # Only one orientation constraint should remain
    assert len(decorators['constraints']) == 1

    yaml_out = serialize_to_yaml_string(decorators)
    # Ensure YAML does not contain duplicate 'orientation:' keys
    assert yaml_out.count('orientation:') == 1


def test_class_and_instance_duplicates_are_deduplicated():
    """If identical annotations appear at the class and instance level, they should be collapsed."""

    @orientation(selector='items', directions=['horizontal'])
    class Thing:
        pass

    t = Thing()
    # Apply same annotation to instance
    annotate_orientation(t, selector='items', directions=['horizontal'])
    # Also add a duplicate directive
    from spytial.annotations import annotate_atomColor
    annotate_atomColor(t, selector='items', value='blue')
    annotate_atomColor(t, selector='items', value='blue')

    decorators = collect_decorators(t)

    # Orientation should be deduplicated (one from class, one from instance -> one total)
    assert sum(1 for c in decorators['constraints'] if 'orientation' in c) == 1
    # atomColor directives should also be deduplicated
    assert sum(1 for d in decorators['directives'] if 'atomColor' in d) == 1

    yaml_out = serialize_to_yaml_string(decorators)
    assert yaml_out.count('orientation:') == 1
    assert yaml_out.count('atomColor:') == 1
