import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException   
from pydantic import BaseModel
import json

DB = '<YOUR DB>'

app = FastAPI()

class IssueIn(BaseModel):
    title: str            
    description: str      
    priority: str         
    assignee_name: str 
    assignee_email : str
    meta: dict | None = None


@app.post("/issues")
def create_issue(issue: IssueIn):
    now = datetime.now().isoformat()
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO resolve_core_issue
               (title, description, priority, status, source,
                assignee_name, assignee_email, meta,
                created_date, inserted_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (issue.title, issue.description, issue.priority, "open", "chatbot",
             issue.assignee_name, issue.assignee_email,
             json.dumps(issue.meta) if issue.meta else None,   
             now, now, now)
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return {"ok": True, "id": new_id, "title": issue.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
