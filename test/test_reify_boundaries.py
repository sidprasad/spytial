"""Executable boundaries for the Python type coverage and reification docs.

Strict expected failures express a desired round-trip property, not approval
of the current loss. If support improves, promote the test and update the
corresponding documentation row. All captures cross a JSON boundary.
"""

import asyncio
import json
import sys
import types

import pytest

from spytial import CnDDataInstanceBuilder, reify, replit


def datum(value):
    return json.loads(json.dumps(CnDDataInstanceBuilder().build_instance(value)))


def roundtrip(value):
    return reify(datum(value))


def function():
    return 7


def generator_function():
    yield 7


async def coroutine_function():
    return 7


async def async_generator_function():
    yield 7


class CallableValue:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value

    def method(self):
        return self.value

    @staticmethod
    def static():
        return 7

    @classmethod
    def class_method(cls):
        return cls


class IntSubclass(int):
    pass


class ListSubclass(list):
    pass


class PrivateState:
    def __init__(self):
        self.__value = 7

    def read(self):
        return self.__value


@pytest.mark.parametrize(
    "value",
    [function, generator_function, coroutine_function,
     async_generator_function, CallableValue.static],
)
def test_named_function_kinds_resolve_by_reference(value):
    assert roundtrip(value) is value


def test_callable_instance_recovers_behavior_and_type():
    original = CallableValue(7)
    restored = roundtrip(original)
    assert type(restored) is CallableValue
    assert restored is not original
    assert restored() == 7


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(object, id="bare-object"),
        pytest.param(lambda: slice(1, 8, 2), id="slice"),
        pytest.param(lambda: function.__code__, id="code"),
        pytest.param(lambda: CallableValue(7).method, id="bound-method"),
        pytest.param(lambda: CallableValue.class_method, id="bound-class-method"),
        pytest.param(lambda: CallableValue.__dict__["static"], id="staticmethod-wrapper"),
        pytest.param(lambda: CallableValue.__dict__["class_method"], id="classmethod-wrapper"),
        pytest.param(lambda: iter([1, 2]), id="iterator"),
        pytest.param(lambda: memoryview(b"abc"), id="memoryview"),
        pytest.param(lambda: types.MappingProxyType({"a": 7}), id="mappingproxy"),
        pytest.param(lambda: {"a": 7}.keys(), id="dict-keys"),
        pytest.param(lambda: IntSubclass(7), id="int-subclass"),
        pytest.param(lambda: ListSubclass([7]), id="list-subclass"),
    ],
)
@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="No dedicated inverse; returns an attribute proxy",
)
def test_unsupported_types_recover_exact_type(factory):
    original = factory()
    try:
        assert type(roundtrip(original)) is type(original)
    finally:
        if isinstance(original, memoryview):
            original.release()


@pytest.fixture
def execution_values():
    # A suspended frame with no caller and a small namespace avoids walking
    # pytest's live frames, globals, and fixtures during the coverage probe.
    namespace = {"__builtins__": {}}
    exec(
        "def gen():\n    yield 7\n"
        "async def coro():\n    return 7\n"
        "async def agen():\n    yield 7\n",
        namespace,
    )
    generator = namespace["gen"]()
    coroutine = namespace["coro"]()
    async_generator = namespace["agen"]()
    frame = generator.gi_frame
    traceback = types.TracebackType(None, frame, frame.f_lasti, frame.f_lineno)
    try:
        yield {
            "generator": generator, "coroutine": coroutine,
            "async-generator": async_generator, "frame": frame,
            "traceback": traceback,
        }
    finally:
        generator.close()
        coroutine.close()
        asyncio.run(async_generator.aclose())


@pytest.mark.parametrize(
    "kind", ["generator", "coroutine", "async-generator", "frame", "traceback"],
)
@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="Captured attributes do not reconstruct execution objects",
)
def test_execution_objects_recover_exact_type(execution_values, kind):
    original = execution_values[kind]
    assert type(roundtrip(original)) is type(original)


@pytest.mark.xfail(
    strict=True, raises=(AssertionError, ValueError),
    reason="File state is not reconstructed, even if its class is allocated",
)
def test_file_recovers_readable_contents_and_position(tmp_path):
    path = tmp_path / "value.txt"
    path.write_text("abcdef", encoding="utf-8")
    with path.open(encoding="utf-8") as original:
        original.read(2)
        restored = roundtrip(original)
        assert type(restored) is type(original)
        assert restored.read() == "cdef"


@pytest.mark.xfail(
    strict=True, raises=AttributeError,
    reason="Generic traversal excludes class-mangled private state",
)
def test_private_state_recovers_method_behavior():
    restored = roundtrip(PrivateState())
    assert type(restored) is PrivateState
    assert restored.read() == 7


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="Tuple root is reconstructed twice before memoization",
)
def test_tuple_cycle_preserves_root_identity():
    items = []
    original = (items,)
    items.append(original)
    restored = roundtrip(original)
    assert restored[0][0] is restored


def test_tuple_cycle_preserves_identity_when_entered_at_list():
    original = []
    original.append((original,))
    restored = roundtrip(original)
    assert restored[0][0] is restored


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="Textual NaN identifiers merge distinct keys",
)
def test_distinct_nan_keys_keep_both_entries():
    original = {float("nan"): "first", float("nan"): "second"}
    assert len(original) == 2
    assert len(roundtrip(original)) == 2


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="Subclass and base value have the same atom identifier",
)
def test_primitive_subclass_and_base_keep_distinct_types():
    restored = roundtrip([IntSubclass(7), 7])
    assert type(restored[0]) is IntSubclass
    assert type(restored[1]) is int


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="References resolve the current name, not the captured binding",
)
def test_reference_rebinding_after_capture_keeps_original(monkeypatch):
    original = function
    captured = datum(original)
    monkeypatch.setattr(sys.modules[__name__], "function", lambda: 8)
    assert reify(captured) is original


@pytest.mark.xfail(
    strict=True, raises=RecursionError, reason="Proxy repr has no recursion guard",
)
def test_cyclic_local_class_has_finite_replit():
    class Local:
        pass

    original = Local()
    original.next = original
    assert isinstance(replit(datum(original)), str)


def test_released_memoryview_fails_during_capture():
    view = memoryview(b"abc")
    view.release()
    with pytest.raises(ValueError, match="released memoryview"):
        datum(view)


def test_can_reify_is_not_a_validation_guarantee():
    malformed = {
        "atoms": [{"id": "n0", "type": "int", "label": "not an integer"}],
        "relations": [], "rootId": "n0",
    }
    builder = CnDDataInstanceBuilder()
    assert builder.can_reify(malformed)
    with pytest.raises(ValueError):
        builder.reify(malformed)
