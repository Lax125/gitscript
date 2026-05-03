import unittest
from pathlib import Path

from utils import run_program

ROOT = Path(__file__).resolve().parents[1]


def run_example(name: str, inputs: list[str] | None = None) -> str:
    return run_program((ROOT / "examples" / name).read_text(encoding="utf-8"), inputs)[1]


class ExampleTests(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(run_example("hello_world.gs"), "Hello, World!\n")

    def test_palindrome(self):
        self.assertEqual(run_example("palindrome.gs", ["aba"]), "aba is a palindrome.\n")
        self.assertEqual(run_example("palindrome.gs", ["abc"]), "abc is not a palindrome.\n")
        self.assertEqual(run_example("palindrome.gs", ["a"]), "a is a palindrome.\n")


if __name__ == '__main__':
    unittest.main()
