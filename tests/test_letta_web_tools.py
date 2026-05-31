import unittest

from letta_web_tools import LETTA_WEB_TOOL_SPECS


def load_function(source_code: str, function_name: str):
    namespace = {}
    exec(source_code, namespace)
    return namespace[function_name]


class LettaWebToolsTest(unittest.TestCase):
    def test_tool_names_are_unique(self) -> None:
        names = [spec.name for spec in LETTA_WEB_TOOL_SPECS]

        self.assertEqual(len(names), len(set(names)))

    def test_fetch_web_text_rejects_non_http_urls(self) -> None:
        spec = next(spec for spec in LETTA_WEB_TOOL_SPECS if spec.name == "fetch_web_text")
        function = load_function(spec.source_code, spec.name)

        result = function("file:///etc/passwd")

        self.assertIn("only http and https are allowed", result)

    def test_fetch_web_text_rejects_localhost(self) -> None:
        spec = next(spec for spec in LETTA_WEB_TOOL_SPECS if spec.name == "fetch_web_text")
        function = load_function(spec.source_code, spec.name)

        result = function("http://127.0.0.1:8283")

        self.assertIn("private, local, or reserved", result)


if __name__ == "__main__":
    unittest.main()
