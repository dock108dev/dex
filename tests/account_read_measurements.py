"""Controlled authority transitions to isolate derived preparation cost from preview."""

import json
import time
import uuid
from unittest.mock import patch

from django.db import connection, transaction

from pokemon_hunter.beta import account_read_build as accounts
from pokemon_hunter.beta import collection, store


def incremental(cx):
    actor = cx["actor"]
    samples = []
    fetched = []
    decoded = []
    sql_timings = {}
    for n in range(20):
        count = 0
        expansions = 0
        original = store.rows
        original_decode = accounts.decode

        def measure(sql, params=()):
            nonlocal count
            result = original(sql, params)
            count += len(result)
            return result

        def decode(row):
            nonlocal expansions
            expansions += 1
            return original_decode(row)

        def measure_sql(execute, sql, params, many, context):
            start = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                sql_timings[sql] = sql_timings.get(sql, 0) + (time.perf_counter() - start) * 1000

        with transaction.atomic():
            before = collection.one(actor, "copy", "scale-copy-0")
            after = dict(before, notes=f"Engineering edit {n}", revision=before["revision"] + 1)
            generation = collection.generation(actor)
            operation = str(uuid.uuid4())
            start = time.perf_counter()
            prior = accounts.before_mutation(actor)
            capture_ms = (time.perf_counter() - start) * 1000
            assert prior is not None
            collection.write_row("copy", after)
            collection.execute(
                "INSERT INTO collection_operations(id,user_id,kind,request,plan,state,changes,generation) VALUES(%s,%s,'edit','{}',%s,'confirmed',%s,%s)",
                [
                    operation,
                    actor.user_id,
                    json.dumps(
                        dict(creates=[], updates=[dict(kind="copy", before=before, after=after)], deletes=[])
                    ),
                    json.dumps([dict(kind="copy", before=before, after=after)]),
                    generation,
                ],
            )
            collection.bump(actor)
            start = time.perf_counter()
            with (
                connection.execute_wrapper(measure_sql),
                patch.object(store, "rows", side_effect=measure),
                patch.object(accounts, "decode", side_effect=decode),
            ):
                accounts.refresh(actor, prior, operation)
            samples.append(capture_ms + (time.perf_counter() - start) * 1000)
            fetched.append(count)
            decoded.append(expansions)
            accounts.state(actor, accounts.catalog_current().token)
    return dict(
        samples_ms=samples,
        worst_ms=max(samples),
        rows_fetched=fetched,
        rows_decoded=decoded,
        sql_execute_totals_ms=sorted(sql_timings.items(), key=lambda item: item[1], reverse=True)[:20],
        conditions="20 sequential controlled SQL authority edits; standard revision capture and refresh hooks; preview/confirm planning excluded",
    )
