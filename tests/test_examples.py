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
        self.assertEqual(run_example("palindrome.gs", ["aba"]), "Word: aba is a palindrome.\n")
        self.assertEqual(run_example("palindrome.gs", ["abc"]), "Word: abc is not a palindrome.\n")
        self.assertEqual(run_example("palindrome.gs", ["a"]), "Word: a is a palindrome.\n")

    def test_fibonacci(self):
        self.assertEqual(run_example("fibonacci.gs", ["0"]), "Sequence length: ")
        self.assertEqual(run_example("fibonacci.gs", ["8"]), "Sequence length: 0\n1\n1\n2\n3\n5\n8\n13\n")

    def test_collatz(self):
        self.assertEqual(run_example("collatz.gs", ["6"]), "Initial number: 6\n3\n10\n5\n16\n8\n4\n2\n1\n")

    def test_primes(self):
        self.assertEqual(run_example("primes.gs", ["1"]), "Max number: ")
        self.assertEqual(run_example("primes.gs", ["20"]), "Max number: 2\n3\n5\n7\n11\n13\n17\n19\n")

    def test_reverse_words(self):
        self.assertEqual(run_example("reverse_words.gs", [""]), "Sentence: \n")
        self.assertEqual(run_example("reverse_words.gs", ["solo"]), "Sentence: solo\n")
        self.assertEqual(run_example("reverse_words.gs", ["hello world"]), "Sentence: world hello\n")
        self.assertEqual(run_example("reverse_words.gs", ["one two three"]), "Sentence: three two one\n")

    def test_word_sort(self):
        prompt = "Word (empty to sort): "
        self.assertEqual(run_example("word_sort.gs", [""]), prompt)
        self.assertEqual(
            run_example("word_sort.gs", ["banana", "apple", "cherry", ""]),
            prompt * 4 + "apple\nbanana\ncherry\n",
        )
        self.assertEqual(
            run_example("word_sort.gs", ["ABC", "ABCD", "AB", ""]),
            prompt * 4 + "AB\nABC\nABCD\n",
        )
        self.assertEqual(
            run_example("word_sort.gs", ["dog", "cat", "cat", "ant", ""]),
            prompt * 5 + "ant\ncat\ncat\ndog\n",
        )

    def test_quine(self):
        self.assertEqual(run_example("quine.gs", [""]), get_example("quine.gs"))


if __name__ == '__main__':
    unittest.main()
