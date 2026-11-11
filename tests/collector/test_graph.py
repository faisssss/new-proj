from collector.graph import edges_from_traces, missing_services


def trace(*spans):
    """Build a small trace in Jaeger's format from (span_id, service, parent_id) tuples."""
    return {
        "spans": [
            {
                "spanID": span_id,
                "processID": service,
                "references": [{"refType": "CHILD_OF", "spanID": parent}]
                if parent
                else [],
            }
            for span_id, service, parent in spans
        ],
        "processes": {service: {"serviceName": service} for _, service, _ in spans},
    }


def test_call_between_services_becomes_edge():
    t = trace(("a", "frontend", None), ("b", "cartservice", "a"))
    assert edges_from_traces([t]) == {("frontend", "cartservice")}


def test_same_service_spans_make_no_edge():
    t = trace(("a", "frontend", None), ("b", "frontend", "a"))
    assert edges_from_traces([t]) == set()


def test_missing_parent_is_skipped():
    t = trace(("b", "cartservice", "not-in-this-trace"))
    assert edges_from_traces([t]) == set()


def test_edges_combine_across_traces():
    t1 = trace(("a", "frontend", None), ("b", "cartservice", "a"))
    t2 = trace(("c", "frontend", None), ("d", "adservice", "c"))
    assert edges_from_traces([t1, t2]) == {
        ("frontend", "cartservice"),
        ("frontend", "adservice"),
    }


def test_missing_services_reports_gap():
    edges = {("frontend", "cartservice")}
    assert missing_services(edges, {"frontend", "cartservice", "adservice"}) == {
        "adservice"
    }
