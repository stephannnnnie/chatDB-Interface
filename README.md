#  ChatDB Interface – Natural Language to SQL & MongoDB

This component of the **ChatDB** project allows users to interact with both **SQL (MySQL)** and **NoSQL (MongoDB)** databases using natural language queries (e.g., "Show me the first 5 employees"). 

It supports:

- **Schema exploration** – Discover tables/collections, view attributes, and sample data.
- **Query execution** – Perform filters, joins, and aggregations with natural language.
- **Data modification** – Add, update, or delete data across both SQL and MongoDB.

The system includes:
- A **shared frontend** (`frontend.html`) with dropdowns to select database type and input queries.
- A **Flask backend** (`app.py`) that routes requests to either the SQL or MongoDB module.
- Two backend components:
  - **SQL module** powered by **LLaMA (via Ollama)**
  - **MongoDB module** powered by **DeepSeek API**



This README provides a step-by-step guide to set up and run the project.

---

### Prerequisites

#### Software & Tools

- Python 3.8+
- **MySQL Server** running locally (with test databases such as `employees`, `sakila`, or `Chinook`)
- **MongoDB Server** running locally (with test databases such as `WorldData`, `ChinaGDP`, `NobelPrize`)
- MySQL user with read/write access (default used: root/[your own password]
- MongoDB typically does not require authentication for local development
- Node-capable browser for front-end interaction
- **Flask** (Python web server)
- DeepSeek API access (via OpenAI SDK) – Required to convert natural language to MongoDB queries
- ollama Python SDK installed (for LLM interaction with llama3)
- A running Ollama server with a local LLaMA3 model loaded:
 ```bash
  ollama run llama3
  ```
#### Python Packages

Install dependencies with:

```bash
pip install flask mysql-connector-python flask-cors pymongo openai
```
> If `ollama` is not installed, follow [https://ollama.com/download](https://ollama.com/download)

---
### File Structure

```
├── app.py # Flask backend entry point (handles both SQL and MongoDB)
├── frontend.html # Shared web interface for natural language queries
├── nl2sql_v2.py # SQL module: intent detection, SQL generation & execution
├── mongodb_component/ # MongoDB module
│ ├── intentHandler.py # Classify input intent (schema/query/modify)
│ ├── deepseekHandler.py # LLM interaction via DeepSeek API
│ ├── schema_tool.py # Tools to fetch structured schema and sample documents for LLM prompt
├── requirements.txt # Python dependencies
├── README.md # Project documentation
├── Datasets
│ ├── Mysql/
│ │ ├── Chinook_MySql.sql # Chinook dataset
│ │ ├── employees.sql # Employees dataset
│ │ ├── sakila-mv-schema.sql # Sakila dataset's schema
│ │ ├── sakila-mv-data.sql # Sakila dataset's data insertion
│ ├── MongoDB/
│ │ ├── ChinaGDP/ # ChinaGDP dataset
│ │ ├── NobelPrize/ # NobelPrize dataset
│ │ ├── WorldData/ # WorldData dataset
```

---
### How to Run

#### 1.Start Databases

Ensure **MySQL** is running and the `employees`, `world`, or `classicmodels` databases are imported.
Ensure **MongoDB** is running locally with databases such as `WorldData`, `ChinaGDP`, and `NobelPrize`.


Update credentials in `nl2sql_v2.py` if needed:

```python
host="localhost",
user="root",
password="YourPassWord",
```

#### 2. DeepSeek API Key Setup

In `app.py`, replace the placeholder in the following line with your own DeepSeek API key:

```python
deepseek_handler = DeepSeekHandler(db_mapping, api_key="Your_DeepSeek_API_Key_Here")
```

#### 3. Start Ollama with LLaMA3

```bash
ollama run llama3
```

> This will be used for:
> - Classifying user intent (schema / query / modification)
> - Translating natural language to SQL

#### 4. Launch Backend (Flask)

```bash
python app.py
```

It should start at: `http://localhost:8080/`

#### 5. Open Frontend

Open `frontend.html` directly in your browser by double-clicking the file or dragging it into a browser window.

The page provides a simple UI to:
- Select the database engine (SQL or MongoDB)
- Choose a test database
- Enter a natural language query
- View the results

Make sure the backend is already running at `http://localhost:8080`, as the frontend sends API requests to that address.

---
### Supported Features

| Feature                               | Description                                                                                                                                                                                                                                       |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Schema Exploration                    | Ask for available tables/collections and their attributes                                                                                                                                                                                         |
| Sample Data Retrieval                 | View examples from a table or collection                                                                                                                                                                                                          |
| MongoDB Query (find, aggregate, join) | e.g., "Find the District with the largest top 3 (skip the first 2) population group by District, only show the fields of District and population." using `$group`, `$sort`, `$skip`, `$project`, `$limit`                                         |
| MongoDB Modification                  | e.g., "Add two new Nobel Prize records. One is for Physics in 2023, awarded to Alice Smith and for research in quantum computing. The other is for Chemistry in 2022, awarded to Carol Zhang for her work on protein folding." using `insertMany` |
| SQL Query (SELECT)                    | e.g., "List the first 10 employees"                                                                                                                                                                                                               |
| SQL Modification                      | e.g., "Add an employee named Alice in marketing"                                                                                                                                                                                                  |
| Safety Guard for SQL                  | Prevents execution of `DROP`, `TRUNCATE`, etc.                                                                                                                                                                                                    |

---
### Notes
- **LLM Dependency**:  
  - SQL query translation and intent classification are handled via the locally hosted `llama3` model using Ollama.
  - MongoDB query generation is handled via the DeepSeek API, accessed through the OpenAI-compatible SDK.
- **Overall Workflow**:  
  For both SQL and MongoDB, the system first classifies the user's intent (e.g., schema, query, or modify), then routes the request to the corresponding handler.  
  Each handler constructs a precise, minimal prompt tailored to that intent and sends it to the LLM (LLaMA or DeepSeek) to generate an executable query.  
  This modular approach improves reliability, reduces unnecessary token usage, and helps control latency and cost.
- **MongoDB Intent Classification**: The MongoDB component uses keyword matching to classify user intent (schema exploration, query, or modification).  
This approach is chosen for time efficiency — it avoids making an extra LLM call for every user input. While it may miss edge cases, it correctly handles the majority of typical queries.  
Using an LLM for intent classification would improve accuracy but significantly increase response time, so the current setup reflects a balance between speed and precision.
- **Security**: A basic SQL validation is implemented, but further sanitization is recommended in production.
- **Limit Clause**: SELECT queries without `LIMIT` will default to 100 rows to prevent overload.

