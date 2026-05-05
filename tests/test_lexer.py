import unittest

from gitscript.lexer import TokenKind, has_unclosed_single_quote, is_separator_token, lex_statement


class LexerTests(unittest.TestCase):
    def test_lexes_keywords_identifiers_ref_operators_and_integer_literals(self):
        tokens = lex_statement("git branch feature/path-1_ok HEAD~1", 1)

        self.assertEqual([token.kind for token in tokens], [
            TokenKind.GIT,
            TokenKind.BRANCH,
            TokenKind.IDENTIFIER,
            TokenKind.HEAD,
            TokenKind.TILDE,
            TokenKind.INT_LITERAL,
        ])
        self.assertEqual([token.value for token in tokens], ["git", "branch", "feature/path-1_ok", "HEAD", "~", "1"])

        tokens = lex_statement("git commit -42", 1)
        self.assertEqual(tokens[2].kind, TokenKind.INT_LITERAL)
        self.assertEqual(tokens[2].value, "-42")

    def test_lexes_separators_and_strategies(self):
        tokens = lex_statement("git cherry-pick HEAD~2..HEAD -s=max && git merge -s is || git commit 0", 1)

        self.assertEqual(
            [token.kind for token in tokens],
            [
                TokenKind.GIT,
                TokenKind.CHERRY_PICK,
                TokenKind.HEAD,
                TokenKind.TILDE,
                TokenKind.INT_LITERAL,
                TokenKind.RANGE,
                TokenKind.HEAD,
                TokenKind.OPTION,
                TokenKind.EQUALS,
                TokenKind.STRATEGY_MAX,
                TokenKind.AND,
                TokenKind.GIT,
                TokenKind.MERGE,
                TokenKind.OPTION,
                TokenKind.CONDITION_IS,
                TokenKind.OR,
                TokenKind.GIT,
                TokenKind.COMMIT,
                TokenKind.INT_LITERAL,
            ],
        )
        self.assertEqual(tokens[7].group, tokens[8].group)
        self.assertEqual(tokens[8].group, tokens[9].group)
        self.assertTrue(is_separator_token(tokens[15]))

        equals_strategy = lex_statement("git cherry-pick main -s=eq", 1)
        self.assertEqual(
            [token.kind for token in equals_strategy[-2:]],
            [TokenKind.EQUALS, TokenKind.STRATEGY_EQ],
        )

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

    def test_lexes_nested_blocks_without_closing_on_string_apostrophes(self):
        tokens = lex_statement("'!git commit -m \"don't\" && '!git commit 2''", 1)

        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].kind, TokenKind.STRING_LITERAL)
        self.assertEqual(tokens[0].value, "!git commit -m \"don't\" && '!git commit 2'")
        self.assertFalse(has_unclosed_single_quote("'!git commit -m \"don't\"'"))
        self.assertTrue(has_unclosed_single_quote("'!git commit -m \"don't\""))

    def test_lexes_triple_quoted_multiline_strings(self):
        tokens = lex_statement('git commit -m """one\n"two"\nthree"""', 1)

        self.assertEqual(tokens[-1].kind, TokenKind.STRING_LITERAL)
        self.assertEqual(tokens[-1].value, 'one\n"two"\nthree')

    def test_does_not_tokenize_comments_or_whitespace(self):
        tokens = lex_statement("   # only a comment", 1)

        self.assertEqual(tokens, [])

    def test_lexes_newlines_as_statement_separators(self):
        tokens = lex_statement("git commit 1 # comment\n\n  git show", 7)

        self.assertEqual(
            [token.kind for token in tokens],
            [
                TokenKind.GIT,
                TokenKind.COMMIT,
                TokenKind.INT_LITERAL,
                TokenKind.NEWLINE,
                TokenKind.NEWLINE,
                TokenKind.GIT,
                TokenKind.SHOW,
            ],
        )
        self.assertTrue(is_separator_token(tokens[3]))
        self.assertTrue(is_separator_token(tokens[4]))
        self.assertEqual(tokens[5].line, 9)

    def test_conflict_markers_are_statement_separators(self):
        tokens = lex_statement("<<<<<<< a\n=======\n>>>>>>> b", 1)

        marker_tokens = [
            token for token in tokens
            if token.kind in {TokenKind.CONFLICT_START, TokenKind.CONFLICT_MIDDLE, TokenKind.CONFLICT_END}
        ]
        self.assertEqual(
            [token.kind for token in marker_tokens],
            [TokenKind.CONFLICT_START, TokenKind.CONFLICT_MIDDLE, TokenKind.CONFLICT_END],
        )
        self.assertTrue(all(is_separator_token(token) for token in marker_tokens))


if __name__ == "__main__":
    unittest.main()
