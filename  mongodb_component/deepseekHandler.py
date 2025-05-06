import json
import re

from mongodb_component.intentHandler import classify_intent
from openai import OpenAI
from mongodb_component.schema_tool import get_structured_schema, extract_schema_for_collection
# from bson import ObjectId
from bson.objectid import ObjectId



class DeepSeekHandler:
    def __init__(self, db_mapping: dict, api_key: str, model: str = "deepseek-chat"):
        self.db_mapping = db_mapping
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model = model


    def extract_target_db_and_collection(self, user_input: str, collection_name: str = None, db_name: str = None):
        if db_name and collection_name:
            db = self.db_mapping.get(db_name)
            for col in db.list_collection_names():
                if col.lower() == collection_name.lower():
                    return db, col
        if db_name:
            db = self.db_mapping.get(db_name)
            user_text = user_input.lower()
            for collection in db.list_collection_names():
                if collection.lower() in user_text:
                    return db, collection
        return None, None

    def handle_user_input(self, user_input: str, db_name: str = None, collection_name: str = None, join_collection: str = None) -> dict:
        intent = classify_intent(user_input)
        if intent == "schema":
            if collection_name:
                # if collection is given，then deduce
                return self.handle_schema(user_input, db_name, collection_name=collection_name)
            else:
                # if collection is not given then let llm handle
                return self.handle_schema(user_input, db_name)
        elif intent == "query":
            return self.handle_query(user_input, db_name, collection_name, join_collection)
        elif intent == "modify":
            return self.handle_modify(user_input, db_name, collection_name)
        else:
            return {"error": "Sorry, I couldn't understand your request."}

    def handle_schema_old(self, user_input: str, db_name: str = None, collection_name: str = None) -> dict:
        text = user_input.lower()
        if (("collection" in text or "collections" in text or "table" in text or
             "tables" in text or "db" in text or "databases" in text or "database" in text)
                and not collection_name):
            if db_name and db_name in self.db_mapping:
                return {
                    "type": "schema",
                    "db": db_name,
                    "collections": self.db_mapping[db_name].list_collection_names()
                }
            else:
                all_collections = {
                    name: db.list_collection_names()
                    for name, db in self.db_mapping.items()
                }
                return {
                    "type": "schema",
                    "collections": all_collections
                }

        if db_name and collection_name:
            db = self.db_mapping.get(db_name)
            if any(k in text for k in ["field", "fields", "column", "columns", "schema", "structure"]):
                def flatten_fields(doc, prefix=""):
                    fields = set()
                    for key, value in doc.items():
                        full_key = f"{prefix}.{key}" if prefix else key
                        fields.add(full_key)
                        if isinstance(value, dict):
                            fields.update(flatten_fields(value, full_key))
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    fields.update(flatten_fields(item, full_key))
                    return fields
                seen_fields = set()
                for doc in db[collection_name].find().limit(20):
                    seen_fields.update(flatten_fields(doc))
                return {
                    "type": "schema",
                    "db": db.name,
                    "collection": collection_name,
                    "fields": sorted(seen_fields)
                }

            if any(k in text for k in ["sample", "samples", "example", "examples"]):
                sample_data = list(db[collection_name].find().limit(3))
                from bson import ObjectId
                sample_data = [
                    {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}
                    for doc in sample_data
                ]
                return {
                    "type": "schema",
                    "db": db.name,
                    "collection": collection_name,
                    "samples": sample_data
                }

        return {
            "type": "error",
            "message": "Sorry, I couldn't determine the schema info you're asking about."
        }

    def get_collection_schema(self, db, collection_name) -> str:
        def flatten_fields(doc, prefix="", out=None):
            if out is None:
                out = {}
            type_map = {
                str: "string",
                int: "number",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object"
            }
            for key, value in doc.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    flatten_fields(value, full_key, out)
                elif isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        out[full_key] = "array<object>"
                        flatten_fields(value[0], full_key, out)
                    else:
                        out[full_key] = type_map.get(type(value), "unknown")
                else:
                    out[full_key] = type_map.get(type(value), "unknown")
            return out
        field_types = {}
        for doc in db[collection_name].find().limit(20):
            flatten_fields(doc, out=field_types)
        schema_lines = [f"- {k}: {v}" for k, v in sorted(field_types.items())]
        schema_info = f"Collection: {collection_name}\nFields:\n" + "\n".join(schema_lines)
        return schema_info

    def classify_schema_intent(self, user_input: str) -> dict:
        """
        Uses LLM to classify user's schema-related natural language question
        into intent types like: list_collections, get_fields, get_samples, etc.
        """
        prompt = f"""
            You are a MongoDB schema assistant. Strictly classify the request into ONE primary intent:
        
            Classify this MongoDB query into ONE intent:
            - list_collections (e.g. "show tables")
            - get_fields (e.g. "what fields does X have?")
            - get_samples (e.g "show 5 records from X")
            - get_schema_for_all (e.g "show all schemas")
            
            Rules:
            1. Pick the MOST SPECIFIC intent
            2. Include "collection" ONLY if:
               - Name is explicitly mentioned
               - Intent is get_fields/get_samples/get_full_schema
            3. For get_samples ONLY:
               - Extract number if specified (e.g "show 3 orders" → 3)
               - Default to 1 if no number given
            
            Return strict JSON format:
            {{
              "intent": "chosen_intent",    // required
              "collection": "",             // optional
              "limit": 1                    // optional, only for get_samples
            }}
            
            Input: {user_input}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "You are a helpful JSON-only assistant that classifies schema-related questions."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            return {"schema intent": "unknown", "error": str(e)}

    def handle_schema(self, user_input: str, db_name: str = None, collection_name: str = None) -> dict:
        db = self.db_mapping.get(db_name)
        if not db:
            return {"type": "error", "message": f"Invalid database name: {db_name}"}

        try:
            if collection_name:
                # ✅ 如果用户传了 collection_name，我们仍调用 LLM 判断 intent，但强制覆盖 collection 字段
                intent_result = self.classify_schema_intent(user_input)
                intent_result["collection"] = collection_name
            else:
                # ❓用户没传 collection_name，LLM 来判断 intent 和 collection
                intent_result = self.classify_schema_intent(user_input)
        except Exception as e:
            return {"type": "error", "message": f"Intent classification failed: {str(e)}"}

        intent = intent_result.get("intent")
        collection = intent_result.get("collection")

        if intent == "list_collections":
            return {
                "type": "schema",
                "db": db_name,
                "collections": db.list_collection_names()
            }

        elif intent == "get_fields" and collection:
            schema = extract_schema_for_collection(db, collection)
            if not schema:
                return {"type": "error", "message": f"Collection '{collection}' not found or empty"}
            return {
                "type": "schema",
                "db": db_name,
                "collection": collection,
                "fields": schema["fields"]
            }

        elif intent == "get_samples" and collection:
            limit = intent_result.get("limit", 3)  # 默认 3 条样例
            sample_docs = list(db[collection].find().limit(limit))
            from bson import ObjectId
            sample_docs = [
                {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}
                for doc in sample_docs
            ]
            return {
                "type": "schema",
                "db": db_name,
                "collection": collection,
                "samples": sample_docs
            }

        # elif intent == "get_full_schema":
        #     full_schema = get_structured_schema(db, db.list_collection_names())
        #     return {
        #         "type": "schema",
        #         "db": db_name,
        #         "full_schema": full_schema
        #     }

        elif intent == "get_schema_for_all":
            return {
                "type": "schema",
                "db": db_name,
                "fields_by_collection": {
                    name: extract_schema_for_collection(db, name)["fields"]
                    for name in db.list_collection_names()
                }
            }
        return {
            "type": "error",
            "message": f"Unrecognized or unsupported schema request (intent: {intent})"
        }

    def handle_query(self, user_input: str, db_name: str = None, collection_name: str = None, join_collection: str = None) -> dict:
        db = self.db_mapping.get(db_name)
        if not db:
            return {"error": f"Invalid db_name: {db_name}. Available: {list(self.db_mapping.keys())}"}

        if collection_name:
            collections = [collection_name]
            if join_collection:
                collections.append(join_collection)
        else:
            collections = db.list_collection_names()

        # get schema_info
        schema_info = get_structured_schema(db, collections)
        print("type of schema_info:", type(schema_info))

        schema_info_str = format_schema_info(schema_info)
        print("Schema Info Preview:\n", schema_info_str[:1000])

        prompt = f"""
            # MongoDB Query Translator
            - Only return valid JSON.
            - Do NOT include any explanations or comments.
            - Do NOT include Mongo shell syntax.
            - The structure must be directly usable in a MongoDB driver like PyMongo.
            - If projecting a nested field like "a.b", do NOT mix "a: 0" and "a.b: 1". Instead, use an alias like "b": "$a.b" and exclude the full "a" by setting "a": 0 or "_id": 0.


            Input natural language, output strictly formatted executable JSON:
            {{
              "collection": "collection_name",
              "command": {{
                "find": {{
                  "filter": {{query_conditions}},
                  "projection": {{field_selection}},  // optional
                  "sort"/"limit"/"skip": ...         // optional
                }}
                OR
                "aggregate": [
                  {{"$match": ...}},
                  {{"$lookup": {{                    // cross-collection query
                    "from": "related_collection",
                    "localField": "local_field",
                    "foreignField": "foreign_field",
                    "as": "output_field"
                  }}}},
                  {{"$group"/"$sort"/"$limit": ...}}
                ]
              }}
            }}
            
            Available collections and fields: {schema_info_str}
            User query: \"\"\"{user_input}\"\"\"
            """
        response = self.query_deepseek(prompt)
        print("Raw LLM response:", response)

        try:
            parsed = json.loads(response)

            # check return from llm contains "collection" and "command" fields
            if "collection" in parsed and "command" in parsed:
                return parsed
            else:
                return {"error": "Response does not contain a valid command-based query structure."}
        except Exception as e:
            return {"error": f"LLM did not return valid JSON: {str(e)}"}




    def handle_modify(self, user_input: str, db_name: str = None, collection_name: str = None) -> dict:
        db = self.db_mapping.get(db_name)
        if not db:
            return {"error": f"Invalid db_name: {db_name}. Available: {list(self.db_mapping.keys())}"}

        # get collection if needed
        if collection_name:
            collections = [collection_name]
        else:
            collections = db.list_collection_names()

        # get formatted schema
        schema_info = get_structured_schema(db, collections)
        schema_info_str = format_schema_info(schema_info)
        print("📊 Schema Info Preview (for Modify):\n", schema_info_str[:1000])

        # LLM prompt for modify
        prompt = f"""
        # MongoDB Modification Translator
        Your job is to convert natural language data modification requests into strict MongoDB JSON syntax.
        
        Output format:
        {{
          "collection": "<name>",
          "action": "insertOne" | "insertMany" | "updateOne" | "updateMany" | "deleteOne" | "deleteMany",
          
          // For insertOne / insertMany:
          "data": {{...}} | [{{...}}],
          
          // For updateOne / updateMany:
          "filter": {{...}},
          "update": {{
            "$set": {{...}},       // Optional: to update fields
            "$inc": {{...}},       // Optional: to increment numbers
            "$unset": {{...}}      // Optional: to remove fields
          }},
          
         // For deleteOne / deleteMany:
          "filter": {{...}}
        }}
        
        Schema info:
        {schema_info_str}
        
        Rules:
        - Use insertMany / updateMany / deleteMany for batch operations.
        - All fields must exist in the schema.
        - DELETE must include a non-empty filter.
        - Return ONLY a strict JSON object. No explanations, no Markdown, no extra text.
        
        User input:
        \"\"\"{user_input}\"\"\"
        """

        # call LLM
        response = self.query_deepseek(prompt)
        print("🔎 Raw Modify LLM Response:", response)
        try:
            parsed = json.loads(response)
        except Exception as e:
            return {"error": f"LLM did not return valid JSON: {str(e)}"}

        # execute MongoDB
        target_collection = parsed.get("collection")
        if not target_collection:
            return {"error": "LLM response missing 'collection'"}
        collection = db[target_collection]
        action = parsed.get("action")
        try:
            # if action == "insertOne":
            #     result = collection.insert_one(parsed.get("data"))
            #     return {
            #         "type": "modify",
            #         "action": "insertOne",
            #         "inserted_id": str(result.inserted_id)
            #     }
            if action == "insertOne":
                result = collection.insert_one(parsed.get("data"))
                return stringify_object_ids({
                    "type": "modify",
                    "action": "insertOne",
                    "inserted_id": result.inserted_id,
                    "inserted_data": parsed.get("data")
                })
            # elif action == "insertMany":
            #     result = collection.insert_many(parsed.get("data"))
            #     return {
            #         "type": "modify",
            #         "action": "insertMany",
            #         "inserted_ids": [str(i) for i in result.inserted_ids]
            #     }
            elif action == "insertMany":
                result = collection.insert_many(parsed.get("data"))
                return stringify_object_ids({
                    "type": "modify",
                    "action": "insertMany",
                    "inserted_ids": result.inserted_ids,
                    "inserted_data": parsed.get("data")
                })
            elif action == "updateOne":
                parsed["filter"] = convert_object_ids(parsed.get("filter", {}))
                parsed["update"] = convert_object_ids(parsed.get("update", {}))
                result = collection.update_one(parsed["filter"], parsed["update"])
                res = {
                    "type": "modify",
                    "action": "update",
                    "matched": result.matched_count,
                    "modified": result.modified_count
                }
                if result.matched_count == 0:
                    res["note"] = "No documents matched the filter."
                return res
            elif action == "updateMany":
                parsed["filter"] = convert_object_ids(parsed.get("filter", {}))
                parsed["update"] = convert_object_ids(parsed.get("update", {}))
                result = collection.update_many(parsed["filter"], parsed["update"])
                res = {
                    "type": "modify",
                    "action": "update",
                    "matched": result.matched_count,
                    "modified": result.modified_count
                }
                if result.matched_count == 0:
                    res["note"] = "No documents matched the filter."
                return res

            elif action == "deleteOne":
                parsed["filter"] = convert_object_ids(parsed.get("filter", {}))
                result = collection.delete_one(parsed["filter"])
                res = {
                    "type": "modify",
                    "action": "deleteOne",
                    "deleted": result.deleted_count
                }
                if result.deleted_count == 0:
                    res["note"] = "No documents matched the filter."
                return res

            elif action == "deleteMany":
                parsed["filter"] = convert_object_ids(parsed.get("filter", {}))
                result = collection.delete_many(parsed["filter"])
                res = {
                    "type": "modify",
                    "action": "deleteMany",
                    "deleted": result.deleted_count
                }
                if result.deleted_count == 0:
                    res["note"] = "No documents matched the filter."
                return res
            else:
                return {"error": f"Unrecognized action: {action}"}
        except Exception as e:
            return {"error": f"MongoDB operation failed: {str(e)}"}






    def query_deepseek(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a MongoDB expert. For each task, the user will give you database name, collection, the schema (with example field types), and a natural language instruction. Your job is to return a **strict MongoDB query** in **JSON format**. Do not include explanations, comments, or any extra text. Only return the JSON object."
},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content
            # clean markdown （```json\n...```）
            clean = re.sub(r"```(?:json)?\n?", "", raw).strip("`\n ")

            return clean
        except Exception as e:
            return f"Error calling DeepSeek: {str(e)}"


# tool function



def format_schema_info(schema_info: dict) -> str:
    text = "Collections and Fields:\n"
    for cname, cinfo in schema_info["collections"].items():
        text += f"  Collection: {cname}\n"
        for fname, ftype in cinfo["fields"].items():
            text += f"    - {fname}: {ftype}\n"
    if schema_info.get("relationships"):
        text += "\nRelationships:\n"
        for rel in schema_info["relationships"]:
            text += f"  - from: {rel['from']} → to: {rel['to']}\n"
    return text

def convert_object_ids(doc):
    if isinstance(doc, dict):
        if "$oid" in doc and len(doc) == 1:
            return ObjectId(doc["$oid"])
        return {k: convert_object_ids(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [convert_object_ids(i) for i in doc]
    return doc

def stringify_object_ids(doc):
    if isinstance(doc, dict):
        return {k: stringify_object_ids(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [stringify_object_ids(i) for i in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc
