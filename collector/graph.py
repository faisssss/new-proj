def edges_from_traces(traces: list[dict]) -> set[tuple[str, str]]:
    """Return (caller, callee) pairs of services found in Jaeger traces."""
    edges = set()
    for trace in traces:
        # Look up every span's service first, because a child can be listed before its parent.
        span_service = {
            span["spanID"]: trace["processes"][span["processID"]]["serviceName"]
            for span in trace["spans"]
        }
        for span in trace["spans"]:
            child = span_service[span["spanID"]]
            for ref in span["references"]:
                if ref["refType"] != "CHILD_OF":
                    continue
                parent = span_service.get(ref["spanID"])
                if parent is not None and parent != child:
                    edges.add((parent, child))
    return edges


def missing_services(edges: set[tuple[str, str]], expected: set[str]) -> set[str]:
    """Return the expected services that appear in no edge."""
    seen = {service for edge in edges for service in edge}
    return expected - seen
