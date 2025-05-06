
# --- Intent Classifier local version ---
def classify_intent(user_input: str) -> str:
    text = user_input.lower().strip()

    modify_keywords = [
        'update', 'change', 'set',
        'insert', 'add',
        'delete', 'remove',
        'edit', 'replace'
    ]
    if any(kw in text for kw in modify_keywords):
        print("Intent classified as modify")
        return 'modify'

    schema_keywords = [
        'collection', 'collections',
        'field', 'fields',
        'column', 'columns',
        'schema', 'structure',
        'sample', 'samples',
        'example', 'examples',
        'table', 'tables',
        'db', 'databases', 'database', 'inside', 'attribute', 'attributes'
    ]
    if any(kw in text for kw in schema_keywords):
        if any(kw in text for kw in ['find', 'where', 'matches', 'search', 'filter']):
            pass
        else:
            print("Intent classified as schema")
            return 'schema'

    query_keywords = [
        'find', 'show', 'list', 'get', 'display', 'retrieve',
        'aggregate', 'match', 'group', 'sort', 'limit', 'skip', 'project',
        'join', 'lookup',
        'average', 'mean', 'sum', 'total', 'count',
        'maximum', 'minimum', 'max', 'min', 'largest', 'top', 'smallest', 'low', 'most'
    ]
    if any(kw in text for kw in query_keywords):
        print("Intent classified as query")
        return 'query'

    # schema_starts = [
    #     'can you tell', 'what is inside', 'what’s inside', 'what is in'
    # ]
    # if any(text.startswith(pfx) for pfx in schema_starts):
    #     return 'schema'

    query_starts = [
        'what is', 'what are', 'what was',
        'how many', 'how much', 'give me', 'can you show'
    ]
    if any(text.startswith(pfx) for pfx in query_starts):
        print("Intent classified as query")
        return 'query'
    print("Intent classified as unknown")
    return 'unknown'
