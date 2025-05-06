from collections import defaultdict

def infer_type(value):
    if isinstance(value, str):
        return "string"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "double"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    elif hasattr(value, "binary"):  # e.g., ObjectId
        return "ObjectId"
    return "unknown"

def extract_schema_for_collection(db, collection_name):
    if collection_name not in db.list_collection_names():
        return None

    collection = db[collection_name]
    sample_docs = list(collection.find().limit(10))
    if not sample_docs:
        return None

    fields = {}

    def parse_doc(d, prefix=""):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                fields[key] = "object"
                parse_doc(v, key)
            elif isinstance(v, list):
                fields[key] = "array"
                if v and isinstance(v[0], dict):
                    parse_doc(v[0], key)
            else:
                fields[key] = infer_type(v)

    for doc in sample_docs:
        parse_doc(doc)

    return {
        "fields": fields,
        "indexes": list(collection.index_information().keys())
    }

def get_structured_schema(db, collections):
    schema_info = {
        "collections": {},
        "relationships": []
    }

    for collection_name in collections:
        col_schema = extract_schema_for_collection(db, collection_name)
        if col_schema:
            schema_info["collections"][collection_name] = col_schema

    # Guess relationships
    for cname, cinfo in schema_info["collections"].items():
        for field, ftype in cinfo["fields"].items():
            if "id" in field.lower() and ftype == "ObjectId":
                parts = field.lower().split("_")
                if len(parts) >= 2:
                    ref_coll = parts[0]  # user_id → user._id
                    if ref_coll in schema_info["collections"]:
                        schema_info["relationships"].append({
                            "from": f"{cname}.{field}",
                            "to": f"{ref_coll}._id"
                        })

    return schema_info
