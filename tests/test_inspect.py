"""Tests extensions to the builtin inspect module.

Note: ``untokenize`` doesn't properly preserve inter-token spacing, so this test vector
may need to change while still remaining valid.
"""


from importlib.machinery import SourceFileLoader

import pytest

import belay.inspect


@pytest.fixture
def foo(data_path):
    fn = data_path / "foo.py"
    foo = SourceFileLoader("foo", str(fn)).load_module()
    assert foo.__file__ == str(fn)
    return foo


def test_getsource_pattern_match():
    pat = belay.inspect._pat_no_decorators
    assert not pat.match("@device.task")
    assert not pat.match("@device.task()")
    assert not pat.match("@device.task(")
    assert not pat.match("")
    assert not pat.match("\n")

    assert pat.match("def foo")
    assert pat.match("def foo()")
    assert pat.match("def foo(")
    assert pat.match("def foo(\n\n")

    assert pat.match("async def foo")
    assert pat.match("async def foo()")
    assert pat.match("async def foo(")
    assert pat.match("async def foo(\n\n")


def test_getsource_basic(foo):
    code, lineno, file = belay.inspect.getsource(foo.foo)
    assert code == "def foo(arg1, arg2):\n    return arg1 + arg2\n"
    assert lineno == 15
    assert file == foo.__file__


def test_getsource_decorated_1(foo):
    code, lineno, file = belay.inspect.getsource(foo.foo_decorated_1)
    assert code == "def foo_decorated_1(arg1, arg2):\n    return arg1 + arg2\n"
    assert lineno == 20
    assert file == foo.__file__


def test_getsource_decorated_2(foo):
    code, lineno, file = belay.inspect.getsource(foo.foo_decorated_2)
    assert code == "def foo_decorated_2(arg1, arg2):\n    return arg1 + arg2\n"
    assert lineno == 25
    assert file == foo.__file__


def test_getsource_decorated_3(foo):
    code, lineno, file = belay.inspect.getsource(foo.foo_decorated_3)
    assert code == "def foo_decorated_3(arg1, arg2):\n    return arg1 + arg2\n"
    assert lineno == 30
    assert file == foo.__file__


def test_getsource_decorated_4(foo):
    code, lineno, file = belay.inspect.getsource(foo.foo_decorated_4)
    assert (
        code
        == "def foo_decorated_4(\n    arg1,\n    arg2,\n):\n    return arg1 + arg2\n"
    )
    assert lineno == 35
    assert file == foo.__file__


def test_getsource_decorated_5(foo):
    """Removes leading indent."""
    code, lineno, file = belay.inspect.getsource(foo.foo_decorated_5)
    assert code == "def foo_decorated_5 (arg1 ,arg2 ):\n    return arg1 +arg2 \n"
    assert lineno == 45
    assert file == foo.__file__


def test_getsource_decorated_6(foo):
    """Double decorated."""
    code, lineno, file = belay.inspect.getsource(foo.foo_decorated_6)
    assert code == "def foo_decorated_6(arg1, arg2):\n    return arg1 + arg2\n"
    assert lineno == 51
    assert file == foo.__file__


def test_getsource_decorated_7(foo):
    """Double decorated."""
    code, lineno, file = belay.inspect.getsource(foo.foo_decorated_7)
    assert (
        code
        == 'def foo_decorated_7(arg1, arg2):\n    return """This\n    is\na\n  multiline\n             string.\n"""\n'
    )
    assert lineno == 56
    assert file == foo.__file__


def test_getsource_nested():
    def foo():
        bar = 5
        return 7

    code, lineno, file = belay.inspect.getsource(foo)
    assert code == "def foo ():\n    bar =5 \n    return 7 \n"
    assert file == __file__


def test_getsource_nested_multiline_string():
    for _ in range(1):

        def foo(arg1, arg2):
            return """This
    is
a
  multiline
             string.
"""

    code, lineno, file = belay.inspect.getsource(foo)
    assert (
        code
        == 'def foo (arg1 ,arg2 ):\n    return """This\n    is\na\n  multiline\n             string.\n"""\n'
    )
    assert file == __file__


def test_getsource_nested_multiline_string():
    # fmt: off
    def bar(a, b):
        return a * b

    for _ in range(1):

        def foo(arg1, arg2):
            return bar(
arg1,
    arg2
)

    # fmt: on
    code, lineno, file = belay.inspect.getsource(foo)
    assert (
        code
        == "def foo (arg1 ,arg2 ):\n    return bar (\n    arg1 ,\n    arg2 \n    )\n"
    )
    assert file == __file__


def test_isexpression_basic():
    assert belay.inspect.isexpression("") == False

    # Basic expressions (True)
    assert belay.inspect.isexpression("1") == True
    assert belay.inspect.isexpression("1 + 2") == True
    assert belay.inspect.isexpression("foo") == True

    # Statements (False)
    assert belay.inspect.isexpression("foo = 1 + 2") == False
    assert belay.inspect.isexpression("if True:\n 1 + 2") == False

    # Invalid syntax (False)
    assert belay.inspect.isexpression("1foo") == False
    assert belay.inspect.isexpression("1+") == False


def test_remove_signature_basic():
    code = "def foo(arg1, arg2):\n    arg1 += 1\n    return arg1 + arg2\n"
    res, lines_removed = belay.inspect._remove_signature(code)
    assert lines_removed == 1
    assert res == "    arg1 += 1\n    return arg1 + arg2\n"


def test_remove_signature_multiline():
    code = "def foo(arg1,\n arg2\n):\n    arg1 += 1\n    return arg1 + arg2\n"
    res, lines_removed = belay.inspect._remove_signature(code)
    assert lines_removed == 3
    assert res == "    arg1 += 1\n    return arg1 + arg2\n"


@pytest.mark.skip(reason="poc for executing body of function. remove later.")
def test_signature_as_globals_poc():
    def foo(arg1, arg2, arg3=1):
        return arg1 + arg2 + arg3

    import inspect
    from functools import wraps

    signature = inspect.signature(foo)

    @wraps(foo)
    def foo_wrapped(*args, **kwargs):
        bound_arguments = signature.bind(*args, **kwargs)
        bound_arguments.apply_defaults()
        arg_assign_cmd = "\n".join(
            f"{name}={repr(val)}" for name, val in bound_arguments.arguments.items()
        )
        print(arg_assign_cmd)

    foo_wrapped("a", "b", "c")
