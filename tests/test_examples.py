import unittest
from pathlib import Path

from utils import run_program

ROOT = Path(__file__).resolve().parents[1]


def get_example(name: str) -> str:
    return (ROOT / "examples" / name).read_text(encoding="utf-8")


def run_example(name: str, inputs: list[str] | None = None) -> str:
    return run_program(get_example(name), inputs)[1]


class ExampleTests(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(run_example("hello_world.gs"), "Hello, World!\n")

    def test_palindrome(self):
        self.assertEqual(run_example("palindrome.gs", ["aba"]), "aba is a palindrome.\n")
        self.assertEqual(run_example("palindrome.gs", ["abc"]), "abc is not a palindrome.\n")
        self.assertEqual(run_example("palindrome.gs", ["a"]), "a is a palindrome.\n")

    def test_fibonacci(self):
        self.assertEqual(run_example("fibonacci.gs", ["0"]), "")
        self.assertEqual(run_example("fibonacci.gs", ["8"]), "0\n1\n1\n2\n3\n5\n8\n13\n")

    def test_collatz(self):
        self.assertEqual(run_example("collatz.gs", ["6"]), "6\n3\n10\n5\n16\n8\n4\n2\n1\n")

    def test_primes(self):
        self.assertEqual(run_example("primes.gs", ["1"]), "")
        self.assertEqual(run_example("primes.gs", ["20"]), "2\n3\n5\n7\n11\n13\n17\n19\n")

    def test_reverse_words(self):
        self.assertEqual(run_example("reverse_words.gs", [""]), "\n")
        self.assertEqual(run_example("reverse_words.gs", ["solo"]), "solo\n")
        self.assertEqual(run_example("reverse_words.gs", ["hello world"]), "world hello\n")
        self.assertEqual(run_example("reverse_words.gs", ["one two three"]), "three two one\n")

    def test_word_sort(self):
        self.assertEqual(run_example("word_sort.gs", [""]), "")
        self.assertEqual(
            run_example("word_sort.gs", ["banana", "apple", "cherry", ""]),
            "apple\nbanana\ncherry\n",
        )
        self.assertEqual(
            run_example("word_sort.gs", ["ABC", "ABCD", "AB", ""]),
            "AB\nABC\nABCD\n",
        )
        self.assertEqual(
            run_example("word_sort.gs", ["dog", "cat", "cat", "ant", ""]),
            "ant\ncat\ncat\ndog\n",
        )

    def test_quine(self):
        self.assertEqual(run_example("quine.gs", [""]), get_example("quine.gs"))


if __name__ == '__main__':
    unittest.main()
