import unittest

from gitscript.lexer import TokenKind, lex_statement


class LexerTests(unittest.TestCase):
    def test_lexes_labels_options_and_integer_literals(self):
        tokens = lex_statement("git branch feature/path-1_ok HEAD~1", 1)

        self.assertEqual([token.kind for token in tokens], [
            TokenKind.LABEL,
            TokenKind.LABEL,
            TokenKind.LABEL,
            TokenKind.WORD,
        ])
        self.assertEqual([token.value for token in tokens], ["git", "branch", "feature/path-1_ok", "HEAD~1"])

        tokens = lex_statement("git commit -42", 1)
        self.assertEqual(tokens[2].kind, TokenKind.INT_LITERAL)
        self.assertEqual(tokens[2].value, "-42")

    def test_lexes_string_literals_and_ignores_comments_outside_quotes(self):
        tokens = lex_statement(r'git commit -m "A#B \"C\"" # comment', 1)

        self.assertEqual(len(tokens), 4)
        self.assertEqual(tokens[3].kind, TokenKind.STRING_LITERAL)
        self.assertEqual(tokens[3].value, 'A#B "C"')
        self.assertTrue(tokens[3].quoted)

    def test_lexes_alias_fragments_as_string_literals(self):
        tokens = lex_statement("git config alias.c 'commit -m'", 1)

        self.assertEqual(tokens[-1].kind, TokenKind.STRING_LITERAL)
        self.assertEqual(tokens[-1].value, "commit -m")

    def test_lexes_triple_quoted_multiline_strings(self):
        tokens = lex_statement('git commit -m """one\n"two"\nthree"""', 1)

        self.assertEqual(tokens[-1].kind, TokenKind.STRING_LITERAL)
        self.assertEqual(tokens[-1].value, 'one\n"two"\nthree')


if __name__ == "__main__":
    unittest.main()
