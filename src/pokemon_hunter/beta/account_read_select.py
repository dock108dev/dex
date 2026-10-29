"""Account membership intersects the shared literal substring gram index."""


def search_ranks(build, stride, query, scope):
    tokens = query.casefold().split()
    grams = sorted(
        {token[i : i + min(3, len(token))] for token in tokens for i in range(max(1, len(token) - 2))}
    )
    prefix = f"{build} AND s{scope} AND "
    positive = " AND ".join("p" + part.encode().hex() for part in tokens)
    fast = prefix + "(" + positive + ")"
    residual = prefix + " AND ".join("g" + gram.encode().hex() for gram in grams) + " NOT (" + positive + ")"
    rank = "(cr_gram_index.rowid-%s)/%s"
    common = " AND ".join("instr(r.search,%s)>0" for _ in tokens)
    child = " AND ".join("instr(c.search,%s)>0" for _ in tokens)
    sql = f"SELECT {rank} FROM cr_gram_index WHERE cr_gram_index MATCH %s UNION ALL SELECT {rank} FROM cr_gram_index JOIN cr_gram_residual r ON r.doc_id=cr_gram_index.rowid WHERE cr_gram_index MATCH %s AND (({common}) OR EXISTS(SELECT 1 FROM cr_match c WHERE c.build=%s AND c.scope IN ('{scope}','shared') AND c.rank_set={rank} AND {child}))"
    return sql, [build, stride, fast, build, stride, residual, *tokens, build, build, stride, *tokens]
