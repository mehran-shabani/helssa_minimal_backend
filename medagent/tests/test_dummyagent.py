from medagent.tests.conftest import DummyAgent


def test_dummy_agent_call():
    agent = DummyAgent()
    assert agent("hi") == "mock assistant reply"
