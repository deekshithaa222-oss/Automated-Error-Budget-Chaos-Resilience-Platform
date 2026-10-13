from chaosgate.prometheus import burn_rate_queries


def test_burn_rate_queries_are_scoped_to_canary_bad_sli_events() -> None:
    by_name = {query.window.name: query for query in burn_rate_queries()}

    assert 'route="canary"' in by_name["page-long"].total_query
    assert 'outcome="bad"' in by_name["page-long"].bad_query
    assert "[1h]" in by_name["page-long"].bad_query
    assert "[6h]" in by_name["ticket-long"].bad_query

