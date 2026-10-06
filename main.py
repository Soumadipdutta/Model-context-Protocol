from fastmcp import FastMCP
import os
import aiosqlite
import sqlite3
import json

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Docker: use DB_PATH=/data/expenses.db
# Local development: defaults to ./data/expenses.db
DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(BASE_DIR, "expenses.db")
)

CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

print(f"Database path: {DB_PATH}")

mcp = FastMCP("ExpenseTracker")


# --------------------------------------------------
# Database initialization
# --------------------------------------------------

def init_db():
    try:
        db_dir = os.path.dirname(DB_PATH)

        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)

            conn.commit()

        print("Database initialized successfully")
        print(f"Database file: {DB_PATH}")

    except Exception as e:
        print(f"Database initialization error: {e}")
        raise


init_db()


# --------------------------------------------------
# Tools
# --------------------------------------------------

@mcp.tool()
async def add_expense(
    date,
    amount,
    category,
    subcategory="",
    note=""
):
    """Add a new expense entry to the database."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                INSERT INTO expenses
                (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note)
            )

            expense_id = cursor.lastrowid

            await conn.commit()

            return {
                "status": "success",
                "id": expense_id,
                "message": "Expense added successfully"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


@mcp.tool()
async def list_expenses(start_date, end_date):
    """List expense entries within an inclusive date range."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                SELECT
                    id,
                    date,
                    amount,
                    category,
                    subcategory,
                    note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )

            rows = await cursor.fetchall()

            columns = [description[0] for description in cursor.description]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error listing expenses: {str(e)}"
        }


@mcp.tool()
async def summarize(start_date, end_date, category=None):
    """Summarize expenses by category within an inclusive date range."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            query = """
                SELECT
                    category,
                    SUM(amount) AS total_amount,
                    COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """

            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += """
                GROUP BY category
                ORDER BY total_amount DESC
            """

            cursor = await conn.execute(query, params)

            rows = await cursor.fetchall()

            columns = [description[0] for description in cursor.description]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error summarizing expenses: {str(e)}"
        }


# --------------------------------------------------
# Resource
# --------------------------------------------------

@mcp.resource(
    "expense:///categories",
    mime_type="application/json"
)
def categories():

    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return json.dumps(
            default_categories,
            indent=2
        )

    except Exception as e:
        return json.dumps({
            "error": f"Could not load categories: {str(e)}"
        })


# --------------------------------------------------
# Start MCP server
# --------------------------------------------------

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000
    )