#!/usr/bin/env python3
"""
Test file to validate group by selector annotation functionality for Issue #17.
"""

import pytest

import spytial
from spytial.annotations import (
    group, annotate_group, annotate,
    collect_decorators, serialize_to_yaml_string
)

def test_selector_based_group_constraint():
    """Test the new selector-based group constraint."""
    # Test with new selector-based parameters
    my_set = {1, 2, 3, 4, 5}
    annotate_group(my_set, selector='{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }', name='rottenFruit')
    
    decorators = collect_decorators(my_set)
    assert len(decorators['constraints']) == 1
    constraint = decorators['constraints'][0]['group']
    assert constraint['selector'] == '{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }'
    assert constraint['name'] == 'rottenFruit'

def test_field_based_group_is_retired():
    """spytial-core 5.0 removed the by-field form, and the error carries the rewrite.

    Core made the old spelling a parse error rather than an ignored key, so an
    old spec fails loudly instead of quietly losing its grouping. Raising at the
    decorator moves that failure to the line that wrote it.
    """
    with pytest.raises(ValueError) as excinfo:
        annotate_group([1, 2, 3, 4, 5], field='elements', groupOn=0, addToGroup=1)

    message = str(excinfo.value)
    assert 'removed in spytial-core 5.0' in message
    assert "group(selector='elements', name='elements')" in message


def test_retired_group_error_rewrites_the_call_it_was_given():
    """The rewrite is the caller's own relation, transposed and restricted as written.

    ``groupOn``/``addToGroup`` named tuple columns; a selector keys on its first
    column, so keying on the later one is the transposed relation. The old
    ``selector`` kept only the tuples whose *first* atom it matched -- a domain
    restriction, which is why it goes inside the transpose and not outside it.
    Both spellings were checked against the conformance harness on either side
    of the bump: they entail the same grouping the by-field form did.
    """
    cases = {
        "group(selector='~worksIn', name='worksIn')":
            dict(field='worksIn', groupOn=1, addToGroup=0),
        "group(selector='Manager <: worksIn', name='worksIn')":
            dict(field='worksIn', groupOn=0, addToGroup=1, selector='Manager'),
        "group(selector='~(Manager <: worksIn)', name='worksIn')":
            dict(field='worksIn', groupOn=1, addToGroup=0, selector='Manager'),
    }
    for rewrite, kwargs in cases.items():
        with pytest.raises(ValueError) as excinfo:
            annotate_group([1, 2, 3], **kwargs)
        assert rewrite in str(excinfo.value)


def test_retired_group_form_raises_on_every_authoring_path():
    """Decorator, object registry and Annotated[...] all reject it the same way."""
    kwargs = dict(field='elements', groupOn=0, addToGroup=1)
    paths = (
        lambda: group(**kwargs),
        lambda: annotate_group([1, 2, 3], **kwargs),
        lambda: spytial.Group(**kwargs),
        lambda: spytial.annotate_type_alias(list[int], 'group', **kwargs),
    )
    for path in paths:
        with pytest.raises(ValueError, match='removed in spytial-core 5.0'):
            path()

def test_selector_group_addedge_direction():
    """addEdge accepts the spytial-core >=2.10 direction values and serializes through."""
    for direction in ('none', 'togroup', 'fromgroup'):
        my_obj = [1, 2, 3]
        annotate_group(
            my_obj,
            selector='{b : Basket, a : Fruit | a in b.fruit}',
            name='byBasket',
            addEdge=direction,
        )
        constraint = collect_decorators(my_obj)['constraints'][0]['group']
        assert constraint['addEdge'] == direction

        yaml_output = serialize_to_yaml_string(collect_decorators(my_obj))
        assert f'addEdge: {direction}' in yaml_output


def test_selector_group_addedge_legacy_boolean():
    """Legacy addEdge=True still validates (spytial-core maps it to 'togroup')."""
    my_obj = [1, 2, 3]
    annotate_group(my_obj, selector='{x : Item | x.hot}', name='hot', addEdge=True)
    constraint = collect_decorators(my_obj)['constraints'][0]['group']
    assert constraint['addEdge'] is True


def test_selector_group_addedge_block_form():
    """GroupEdge (spytial-core 3.0) styles the connector; `points` matches the YAML key."""
    from spytial import GroupEdge, LineStyle, TextStyle

    my_obj = [1, 2, 3]
    annotate_group(
        my_obj,
        selector='{b : Basket, a : Fruit | a in b.fruit}',
        name='byBasket',
        addEdge=GroupEdge(
            points='togroup',
            lineStyle=LineStyle(pattern='dashed'),
            textStyle=TextStyle(size='small'),
        ),
        textStyle=TextStyle(color='navy'),
    )
    constraint = collect_decorators(my_obj)['constraints'][0]['group']
    assert constraint['addEdge'] == {
        'points': 'togroup',
        'lineStyle': {'pattern': 'dashed'},
        'textStyle': {'size': 'small'},
    }
    # The group's own label styling is a sibling of addEdge.
    assert constraint['textStyle'] == {'color': 'navy'}

    yaml_output = serialize_to_yaml_string(collect_decorators(my_obj))
    assert 'points: togroup' in yaml_output
    assert 'pattern: dashed' in yaml_output


def test_selector_group_addedge_block_dict_form():
    """The dict escape hatch is the YAML block verbatim."""
    my_obj = [1, 2, 3]
    annotate_group(
        my_obj,
        selector='{x : Item | x.hot}',
        name='hot',
        addEdge={'points': 'fromgroup', 'lineStyle': {'color': 'red'}},
    )
    constraint = collect_decorators(my_obj)['constraints'][0]['group']
    assert constraint['addEdge'] == {
        'points': 'fromgroup',
        'lineStyle': {'color': 'red'},
    }


def test_group_decorator_documents_addedge_directions():
    """@group takes **kwargs, so its docstring is the only place help() can show
    the addEdge surface. Keep the three directions discoverable from the decorator."""
    doc = group.__doc__
    assert doc, "@group needs a docstring; **kwargs tells help() nothing"
    for direction in ('none', 'togroup', 'fromgroup'):
        assert f"'{direction}'" in doc
    assert 'GroupEdge' in doc
    assert 'textStyle' in doc
    # help() reports the decorator by name, not as the factory's inner function.
    assert group.__name__ == 'group'


def test_group_decorator_with_selector():
    """Test the group decorator with selector parameters."""
    my_dict = {'a': 1, 'b': 2}
    my_dict = group(selector='{x : Item | x.type = "special"}', name='specialItems')(my_dict)
    
    decorators = collect_decorators(my_dict)
    assert len(decorators['constraints']) == 1
    constraint = decorators['constraints'][0]['group']
    assert constraint['selector'] == '{x : Item | x.type = "special"}'
    assert constraint['name'] == 'specialItems'

def test_class_level_selector_group():
    """Test class-level selector-based group decorator."""
    @group(selector='{x : Item | x.value > 10}', name='highValueItems')
    class DataContainer:
        def __init__(self, data):
            self.data = data
    
    container = DataContainer({'a': 15, 'b': 5})
    decorators = collect_decorators(container)
    
    assert len(decorators['constraints']) == 1
    constraint = decorators['constraints'][0]['group']
    assert constraint['selector'] == '{x : Item | x.value > 10}'
    assert constraint['name'] == 'highValueItems'

def test_yaml_serialization_matches_issue_requirements():
    """Test that YAML output matches the exact format requested in Issue #17."""
    my_obj = [1, 2, 3]
    annotate_group(my_obj, selector='{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }', name='rottenFruit')
    
    decorators = collect_decorators(my_obj)
    yaml_output = serialize_to_yaml_string(decorators)
    
    # Check that the YAML contains expected elements matching the issue
    assert 'constraints:' in yaml_output
    assert 'group:' in yaml_output
    assert 'selector:' in yaml_output
    assert 'name: rottenFruit' in yaml_output
    assert 'Basket' in yaml_output and 'Fruit' in yaml_output

def test_group_constraints_coexist():
    """Two groups over the same object are two constraints, not one overwriting the other."""
    my_list = [1, 2, 3]

    annotate_group(my_list, selector='items', name='items')
    annotate_group(my_list, selector='{x : Item | x.value < 3}', name='smallItems')

    groups = [entry['group'] for entry in collect_decorators(my_list)['constraints']]
    assert [(g['selector'], g['name']) for g in groups] == [
        ('items', 'items'),
        ('{x : Item | x.value < 3}', 'smallItems'),
    ]

if __name__ == "__main__":
    print("Testing Issue #17: Group by selector annotation")
    
    test_field_based_group_still_works()
    print("✓ Field-based group constraint still works")
    
    test_selector_based_group_constraint()
    print("✓ Selector-based group constraint works")
    
    test_group_decorator_with_selector()
    print("✓ Group decorator with selector works")
    
    test_class_level_selector_group()
    print("✓ Class-level selector group works")
    
    test_yaml_serialization_matches_issue_requirements()
    print("✓ YAML serialization matches issue requirements")
    
    test_both_group_types_coexist()
    print("✓ Both group types can coexist")
    
    print("\n🎉 All Issue #17 tests passed!")