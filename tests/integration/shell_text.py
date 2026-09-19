"""Shell-source helpers shared by the tests that read check scripts as text.

``code_part`` is the one place a shell line's comment is stripped. Both routing tests
used to do ``line.split("#", 1)[0]``, which treats a ``#`` inside quotes as a comment:
``: "#hide" ; python3 - …`` is ordinary bash that runs ``python3``, and the naive split
hid it from both scanners at once (third review of #241). A ``#`` starts a comment only
outside quotes and at the start of a word, as it does for bash.
"""

_WORD_BREAK = " \t;&|()<>"


def code_part(line: str) -> str:
    """``line`` up to its comment, if it has one; quotes and escapes respected."""
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote == "'":
            if ch == "'":
                quote = ""
        elif ch == "\\":
            i += 1  # the next character is literal (outside single quotes)
        elif quote == '"':
            if ch == '"':
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in _WORD_BREAK):
            return line[:i]
        i += 1
    return line
