trace = {
    "spans": [
        {"spanID": "a", "processID": "p1", "references": []},
        {"spanID": "b", "processID": "p2", "references": [{"refType": "CHILD_OF", "spanID": "a"}]},
        {"spanID": "c", "processID": "p3", "references": [{"refType": "CHILD_OF", "spanID": "b"}]},
        {"spanID": "d", "processID": "p2", "references": [{"refType": "CHILD_OF", "spanID": "b"}]},
    ],
    "processes": {
        "p1": {"serviceName": "frontend"},
        "p2": {"serviceName": "checkoutservice"},
        "p3": {"serviceName": "paymentservice"},
    },
}

span_service = {}

for span in trace["spans"]:
    code = span["processID"]
    name = trace["processes"][code]["serviceName"]
    span_service[span["spanID"]] = name

edges = set()

for span in trace["spans"]:
    child_service = span_service[span["spanID"]]
    for ref in span["references"]:
        parent_service = span_service.get(ref["spanID"])
        # Your code goes here
        

print(edges)