import pytest

import belay
from belay import Device


def test_setup_basic(emulated_device):
    @emulated_device.setup
    def setup(config):
        foo = config["bar"]  # noqa: F841

    setup({"bar": 25})

    assert {"bar": 25} == emulated_device("config")
    assert emulated_device("foo") == 25


def test_task_basic(emulated_device, mocker):
    spy_parse_belay_response = mocker.spy(belay.device, "parse_belay_response")

    @emulated_device.task
    def foo(val):
        return 2 * val

    assert foo(5) == 10

    spy_parse_belay_response.assert_called_once_with("_BELAYR10\r\n")


def test_task_generators_basic(emulated_device, mocker):
    spy_parse_belay_response = mocker.spy(belay.device, "parse_belay_response")

    @emulated_device.task
    def my_gen(val):
        i = 0
        while True:
            yield i
            i += 1
            if i == val:
                break

    actual = list(my_gen(3))
    assert actual == [0, 1, 2]
    spy_parse_belay_response.assert_has_calls(
        [
            mocker.call("_BELAYR0\r\n"),
            mocker.call("_BELAYR1\r\n"),
            mocker.call("_BELAYR2\r\n"),
            mocker.call("_BELAYS\r\n"),
        ]
    )


def test_task_generators_communicate(emulated_device):
    @emulated_device.task
    def my_gen(x):
        x = yield x
        x = yield x

    generator = my_gen(5)
    actual = []
    actual.append(generator.send(None))
    actual.append(generator.send(25))
    with pytest.raises(StopIteration):
        generator.send(50)
    assert [5, 25] == actual


def test_teardown(emulated_device, mocker):
    @emulated_device.teardown
    def foo():
        pass

    mock_teardown = mocker.MagicMock()
    assert len(emulated_device._belay_teardown._belay_executers) == 1
    emulated_device._belay_teardown._belay_executers[0] = mock_teardown

    emulated_device.close()

    mock_teardown.assert_called_once()


def test_classdecorator_setup():
    @Device.setup
    def foo1():
        pass

    @Device.setup()
    def foo2():
        pass

    @Device.setup(autoinit=True)
    def foo3():
        pass

    with pytest.raises(ValueError):
        # Provided an arg with autoinit=True is not allowed.

        @Device.setup(autoinit=True)
        def foo(arg1=1):
            pass
