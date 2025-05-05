# chatDB-Interface
## 1. ChatDB SQL Interface – Natural Language to SQL

This component of the **ChatDB** project allows users to interact with SQL databases using natural language queries (e.g., "Show me the first 5 employees"). It supports:

- Schema exploration
- Query translation & execution
- Data modification (insert, update, delete)

This README provides a step-by-step guide to set up and run the SQL portion of the project.

---

### Prerequisites

#### Software & Tools

- Python 3.8+
- MySQL Server running locally (with test databases such as `employees`, `sakila`, or `Chinook`)
- MySQL user with read/write access (default used: root/[your own password]
- Node-capable browser for front-end interaction
- Flask (Python web server)
- ollama Python SDK installed (for LLM interaction with llama3)
- A running Ollama server with a local LLaMA3 model loaded:
 ```bash
  ollama run llama3
  ```
#### Python Packages

Install dependencies with:

```bash
pip install flask mysql-connector-python
```
> If `ollama` is not installed, follow [https://ollama.com/download](https://ollama.com/download)

---
### File Structure

```
├── app.py                # Flask server endpoint for SQL query handling
├── nl2sql_v2.py          # Core logic: intent detection, SQL generation & execution
├── frontend.html         # Web interface (static HTML + JS)
```

---
### How to Run

#### 1. Start MySQL and Import Databases

Ensure MySQL is running and the `employees`, `world`, or `classicmodels` databases are imported.

Update credentials in `nl2sql_v2.py` if needed:

```python
host="localhost",
user="root",
password="YourPassWord",
```
#### 2. Start Ollama with LLaMA3

```bash
ollama run llama3
```

> This will be used for:
> - Classifying user intent (schema / query / modification)
> - Translating natural language to SQL

#### 3. Launch Backend (Flask)

```bash
python app.py
```

It should start at: `http://localhost:5000/`

#### 4. Open Frontend

Open `frontend.html` in a browser directly (double-click or drag into browser).

---
### Supported Features

| Feature            | Description                                               |
|--------------------|-----------------------------------------------------------|
| Schema Exploration | e.g., "What tables are in employees database?"            |
| SQL Query (SELECT) | e.g., "List the first 10 employees"                       |
| SQL Modification   | e.g., "Add an employee named Alice in marketing"          |
| Safety Guard       | Prevents execution of `DROP`, `TRUNCATE`, etc.            |

---
### Notes

- **Security**: A basic SQL validation is implemented, but further sanitization is recommended in production.
- **Limit Clause**: SELECT queries without `LIMIT` will default to 100 rows to prevent overload.
- **LLM Dependency**: All translation and explanation logic relies on the `llama3` model via Ollama.
