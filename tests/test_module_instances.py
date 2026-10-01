import tempfile
import unittest
from pathlib import Path

from repo_doctor.index import build_index


CLASS = "class Client:\n    def send(self):\n        return 1\n"
CALL = "def run():\n    return client.send()\n"
BIND = "client = Client()\n"

POSITIVES = {
    "plain": CLASS + BIND + CALL,
    "annotated": CLASS + "client: Client = Client()\n" + CALL,
    "constructor_name_is_caller_parameter": (
        CLASS + BIND + "def run(Client):\n    return client.send()\n"
    ),
    "unrelated_local_receiver": (
        CLASS + BIND + CALL
        + "def other(client):\n    return client.send()\n"
    ),
}

NEGATIVES = {
    "conditional": CLASS + "if flag:\n    client = Client()\n" + CALL,
    "repeated": CLASS + BIND + BIND + CALL,
    "reassigned": CLASS + BIND + "client = None\n" + CALL,
    "deleted": CLASS + BIND + "del client\n" + CALL,
    "factory": CLASS + "client = factory()\n" + CALL,
    "imported_instance": CLASS + "from provider import client\n" + CALL,
    "wildcard_import": CLASS + BIND + "from provider import *\n" + CALL,
    "definition_default_rebinds_instance": (
        CLASS + BIND
        + "def reset(value=(client := None)):\n    return value\n" + CALL
    ),
    "class_import_collision": "from provider import Client\n" + CLASS + BIND + CALL,
    "class_rebound": CLASS + "Client = object\n" + BIND + CALL,
    "parameter_shadow": CLASS + BIND + "def run(client):\n    return client.send()\n",
    "nested_scope": (
        CLASS + BIND
        + "def outer(client):\n    def run():\n        return client.send()\n"
    ),
    "function_defined_before_binding": CLASS + CALL + BIND,
    "global_write": (
        CLASS + BIND
        + "def reset():\n    global client\n    client = None\n" + CALL
    ),
    "instance_method_patch": CLASS + BIND + "client.send = lambda: 2\n" + CALL,
    "class_method_patch": CLASS + BIND + "Client.send = lambda self: 2\n" + CALL,
    "escaped_alias": CLASS + BIND + "alias = client\n" + CALL,
    "passed_to_callback": CLASS + BIND + "configure(client)\n" + CALL,
    "setattr": CLASS + BIND + "setattr(client, 'send', replacement)\n" + CALL,
    "reflective_globals": CLASS + BIND + "globals()['client'] = replacement\n" + CALL,
    "decorated_method": (
        "class Client:\n    @staticmethod\n    def send():\n        return 1\n"
        + BIND + CALL
    ),
    "inherited_class": CLASS.replace("class Client:", "class Client(Base):") + BIND + CALL,
    "metaclass": CLASS.replace("class Client:", "class Client(metaclass=Meta):") + BIND + CALL,
    "custom_new": (
        "class Client:\n    def __new__(cls):\n        return None\n"
        "    def send(self):\n        return 1\n" + BIND + CALL
    ),
    "self_method_patch": (
        "class Client:\n    def __init__(self):\n        self.send = lambda: 2\n"
        "    def send(self):\n        return 1\n" + BIND + CALL
    ),
    "method_default_rebinds_method": (
        "class Client:\n    def send(self):\n        return 1\n"
        "    def configure(self, value=(send := replacement)):\n        return value\n"
        + BIND + CALL
    ),
    "ambiguous_class": CLASS + CLASS + BIND + CALL,
}


class ModuleInstanceTests(unittest.TestCase):
    def index_for(self, source):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "app.py").write_text(source, encoding="utf-8")
        return build_index(root)

    def test_supported_module_instance_calls(self):
        for name, source in POSITIVES.items():
            with self.subTest(case=name):
                index = self.index_for(source)
                matches = [
                    edge for edge in index.call_edges
                    if edge.caller == "app.py::run"
                    and edge.callee == "app.py::Client.send"
                ]
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0].line, 6)
                self.assertEqual(index.parse_errors, [])

    def test_uncertain_module_instance_calls_remain_unresolved(self):
        for name, source in NEGATIVES.items():
            with self.subTest(case=name):
                index = self.index_for(source)
                self.assertEqual(index.parse_errors, [])
                self.assertFalse(
                    any(edge.callee == "app.py::Client.send" for edge in index.call_edges)
                )


if __name__ == "__main__":
    unittest.main()
