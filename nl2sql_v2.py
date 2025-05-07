
import ollama
import mysql.connector
import re

# Connect to MySQL database
def connect_to_db(database):
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="********",
        database=database
    )
    
# conn = connect_to_db("employees")
def get_schema_text(conn):
    cursor = conn.cursor()

    # Retrieve schema information
    cursor.execute("SHOW TABLES;")
    tables = [row[0] for row in cursor.fetchall()]

    schema_info = {}
    for table in tables:
        cursor.execute(f"DESCRIBE {table};")
        columns = [(row[0], row[1]) for row in cursor.fetchall()] 
        schema_info[table] = columns

    schema_text = "\\n".join([f"{table}: " + ", ".join(f"{col} ({typ})" for col, typ in cols) for table, cols in schema_info.items()])
    return schema_info, schema_text

# Intent Classification using LLM
def classify_intent(query):
    system_prompt = "You are a SQL assistant. Given a user's natural language request, classify it into one of the following types: 'schema', 'query', or 'modification'.\nOnly return one of these words, and nothing else."
    user_prompt = f"User request: {query}"
    response = ollama.chat(model='llama3', messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ])
    raw = response['message']['content'].strip().lower()
    intent = raw.replace('"', '').replace("'", "").strip()
    print(f"Intent classified as: {intent}")
    return intent

# Schema Exploration Handler
def handle_schema_query(query, schema_text):
    prompt = f"""
You are a database assistant. The following is the schema of a MySQL database:

{schema_text}

The user is asking about the database schema—such as what tables exist, what columns are in a table, or requesting sample data from a table.
Please respond appropriately based on the question. Do not generate SQL.

User question: {query}
"""
    # print(schema_text)
    response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
    return {"answer": response['message']['content'].strip()}

# SELECT Query Handler
def handle_select_query(nl_query, schema_text):
    prompt = f"""
You are a helpful assistant that translates natural language into SQL SELECT queries for a MySQL database.

Database Schema:
{schema_text}

The user's request is a SELECT query. Convert the following natural language request into an appropriate SQL SELECT statement.
Only return the SQL. Do not include explanations or commentary. Do NOT include any markdown (like ``` or "sql").
Use only table and column names as shown in the schema.
Query: {nl_query}
"""
    response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()

# Modification Handler (INSERT/UPDATE/DELETE)
def handle_modify_query(nl_query,schema_text):
    prompt = f"""
Database Schema:
{schema_text}

The user's request is to modify the database. Convert the following natural language request into an appropriate SQL statement (INSERT, UPDATE, or DELETE).
Only return the SQL. Do not include explanations or commentary.

Query: {nl_query}
"""
    response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()

# Generate brief explanation (for SELECT results)
def explain_result(nl_query, sql_query, results):
    sample_text = "\n".join([", ".join(map(str, row)) for row in results[:3]])
    prompt = f"""
The user asked: "{nl_query}"
The SQL you generated is: {sql_query}
Here are the top few rows of the result:
{sample_text}
Write a short (1–2 sentence) explanation of what this result shows, in plain English:
"""
    response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()


def enforce_limit(sql_query, max_limit=100):
    if sql_query.strip().upper().startswith("SELECT") and "LIMIT" not in sql_query.upper():
        return sql_query.rstrip(";") + f" LIMIT {max_limit};"
    return sql_query

def validate_safe_sql(sql):
    sql = sql.lower()
    forbidden = ["drop", "truncate", "alter", "create", "grant", "revoke"]
    if any(cmd in sql for cmd in forbidden):
        return "Error: Dangerous SQL command detected."
    return None

# SQL Execution Function
def execute_sql(sql_query, conn,schema_info, original_question=None):
    sql_query = enforce_limit(sql_query)
    validation_error = validate_safe_sql(sql_query)
    if validation_error:
        return {"error": validation_error}
    try:            
        cursor = conn.cursor()
        sql_type = sql_query.split()[0].upper()
        if sql_type == "SELECT":
            print(f"Executing SQL: {sql_query}")
            cursor.execute(sql_query)
            results = cursor.fetchall()
            if not results:
                return {
                    "sql": sql_query,
                    "results": [],
                    "explanation": f"No results found for your query: \"{original_question}\""
                }
            explanation = explain_result(original_question, sql_query, results)
            return {
                "sql": sql_query,
                "results": results,
                "explanation": explanation
            }
        else:
            print(f"Executing SQL: {sql_query}")
            cursor.execute(sql_query)
            conn.commit()
            return {
                "sql": sql_query,
                "status": f"{sql_type} executed successfully."
            }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()

# Main dispatcher
def handle_query(query,database):
    conn = connect_to_db(database)
    schema_info, schema_text = get_schema_text(conn)
    intent = classify_intent(query)
    if intent == "schema":
        result = handle_schema_query(query, schema_text)
        print(result)
        return result
    elif intent == "query":
        sql = handle_select_query(query, schema_text)
        return execute_sql(sql, conn, schema_info, query)
    elif intent == "modification":
        sql = handle_modify_query(query, schema_text)
        return execute_sql(sql, conn, schema_info, query)
    else:
        return {"error": f"Unrecognized request type: {intent}"}

# CLI interface
if __name__ == "__main__":
    user_input = input("How can I help you today?\n> ")
    result = handle_query(user_input, "employees")

    if "error" in result:
        print("\nError:", result["error"])
    elif "answer" in result:
        print("\n", result["answer"])
    elif "results" in result:
        print("\nQuery Results:")
        for row in result["results"]:
            print(row)
        # print("\nExplanation:")
        print(result["explanation"])
    else:
        print("\n", result.get("status", "Done."))
