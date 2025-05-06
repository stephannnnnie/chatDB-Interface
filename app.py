from pymongo import MongoClient
from flask import Flask, request, jsonify, Response
from nl2sql_v2 import handle_query
import json
# from mongodb_component import gptHandler
# from mongodb_component.llamaHandler import LlamaHandler
from mongodb_component.deepseekHandler import DeepSeekHandler
from flask_cors import CORS



app = Flask(__name__)
CORS(app)


# MongoDB connection (single instance with multiple databases)
MONGO_URI = "mongodb://localhost:27017"
client = MongoClient(MONGO_URI)

# Set up mapping to multiple databases
db_mapping = {
    "WorldData": client["WorldData"],
    "ChinaGDP": client["ChinaGDP"],
    "NobelPrize": client["NobelPrize"]
    # "Pokedex": client["Pokedex"],
    # "WorldData": client["WorldData"]
    # "SchoolDB": client["SchoolDB"]
}
# Initialize DeepSeekHandler
deepseek_handler = DeepSeekHandler(db_mapping, api_key="Your_DeepSeek_API_Key_Here")

# Initialize the LlamaHandler with a specific collection
# llama_handler = LlamaHandler(db_mapping)


@app.route('/', methods=['GET'])
def home():
    return "Welcome to ChatDB API!", 200

@app.route('/check_connection', methods=['GET'])
def check_connection():
    try:
        client.admin.command('ping')
        return "Connected to MongoDB successfully.", 200
    except Exception as e:
        return f"Failed to connect to MongoDB: {str(e)}", 500

# @app.route('/test_llama', methods=['GET'])
# def test_llama():
#     prompt = """
#     Return only the following JSON in strict format:
#     {
#       "message": "Llama is alive"
#     }
#     Do not explain anything, do not add Markdown.
#     Only return the raw JSON.
#     """
#     response = llama_handler.query_llama(prompt)
#     return jsonify({"llm_response": response})


@app.route('/test_deepseek', methods=['GET'])
def test_deepseek():
    prompt = """
    Return only the following JSON in strict format:
    {
      "message": "DeepSeek is alive"
    }
    Do not explain anything, do not add Markdown.
    Only return the raw JSON.
    """
    response = deepseek_handler.query_deepseek(prompt)
    try:
        parsed = json.loads(response)
        return jsonify(parsed), 200
    except Exception:
        return jsonify({"raw_response": response}), 500


@app.route('/query/mongodb', methods=['POST'])
def query_mongodb():
    try:
        client.admin.command('ping')  # 检查 MongoDB

        data = request.get_json()
        user_input = data.get('user_input')
        db_name = data.get('db_name')
        collection_name = data.get('collection')  # optional
        join_collection = data.get('join_collection')  # optional

        # check user_input
        if not user_input or not db_name:
            return jsonify({"error": "Missing 'user_input' or 'db_name' in request."}), 400

        # check if the db is existed
        if db_name not in db_mapping:
            return jsonify({"error": f"Invalid db_name. Available: {list(db_mapping.keys())}"}), 400

        # get instance
        db = db_mapping[db_name]
        response = deepseek_handler.handle_user_input(user_input, db_name, collection_name, join_collection)
        print("LLM response:", response)

        if "error" in response:
            return jsonify(response), 400

        # schema
        if response.get("type") == "schema":
            return jsonify(response), 200

        # target_collection = response.get("collection") or \
        #                     response.get("find") or \
        #                     response.get("insert") or \
        #                     response.get("update") or \
        #                     response.get("delete")
        #
        # if not target_collection:
        #     return jsonify({"error": "Collection name not found in LLM response"}), 400

        # collection = db[target_collection]

        # query
        if "command" in response:
            # command = response["command"]
            # target_collection = response.get("collection")
            # if not target_collection:
            #     return jsonify({"error": "Missing 'collection' field in response"}), 400
            #
            # collection = db[target_collection]
            target_collection = response.get("collection")
            if not target_collection:
                return jsonify({"error": "Missing 'collection' field in LLM response"}), 400

            collection = db[target_collection]
            command = response["command"]

            # find
            if "find" in command:
                find_block = command["find"]
                filter_ = find_block.get("filter", {})
                projection = find_block.get("projection")
                sort = find_block.get("sort")
                limit = find_block.get("limit")

                cursor = collection.find(filter_, projection)
                if sort:
                    cursor = cursor.sort(list(sort.items()))
                if limit:
                    cursor = cursor.limit(limit)

                results = list(cursor)
                return jsonify({"result": results}), 200

            # aggregate
            elif "aggregate" in command:
                pipeline = command["aggregate"]
                results = list(collection.aggregate(pipeline))
                return jsonify({"result": results}), 200

        # modify
        elif response.get("type") == "modify":
            return jsonify(response), 200

        return jsonify({"error": "Unsupported operation type"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/query/sql", methods=["POST"])
def query_handler():
    data = request.get_json()
    # if not data or "question" not in data:
    #     return jsonify({"error": "Missing 'question' field"}), 400

    question = data.get("user_input")
    database = data.get("db_name", "employees")
    result = handle_query(question, database)

    return Response(json.dumps(result, indent=2), content_type="application/json")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)



# @app.route('/query/mysql', methods=['POST'])





