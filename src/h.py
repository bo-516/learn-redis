def S(level, q, options, answer, explain, hot=False, snippet=None):
    return dict(type="single", level=level, q=q, options=options, answer=answer, explain=explain.strip(), hot=hot, snippet=snippet)
def M(level, q, options, answer, explain, hot=False, snippet=None):
    return dict(type="multi", level=level, q=q, options=options, answer=answer, explain=explain.strip(), hot=hot, snippet=snippet)
def T(level, q, answer, explain, hot=False, snippet=None):
    return dict(type="tf", level=level, q=q, answer=answer, explain=explain.strip(), hot=hot, snippet=snippet)
def F(level, q, answers, explain, hot=False, snippet=None):
    return dict(type="fill", level=level, q=q, answer=answers, explain=explain.strip(), hot=hot, snippet=snippet)
def B(level, title, answer, deep=None, hot=False):
    return dict(level=level, title=title, answer=answer.strip(), deep=deep.strip() if deep else None, hot=hot)
