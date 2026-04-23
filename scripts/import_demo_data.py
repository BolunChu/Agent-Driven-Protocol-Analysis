"""Demo data import script — seeds the database with FTP sample data."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from pathlib import Path
from sqlmodel import Session
from app.core.database import engine, create_db_and_tables
from app.models.domain import ProtocolProject, SessionTrace


def main():
    create_db_and_tables()
    project_root = Path(__file__).resolve().parents[1]

    with Session(engine) as session:
        # Create project
        project = ProtocolProject(
            name="FTP Protocol Analysis Demo",
            protocol_name="FTP",
            description="Demo analysis of FTP protocol using multi-agent framework",
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        print(f"Created project: {project.name} (id={project.id})")

        # Import doc
        doc_path = project_root / "data" / "docs" / "ftp_summary.md"
        if doc_path.exists():
            doc_content = doc_path.read_text()
            trace = SessionTrace(
                project_id=project.id,
                source_type="doc",
                raw_content=doc_content,
            )
            session.add(trace)
            print(f"Imported doc: {doc_path.name}")

        # Import traces (split by ---)
        trace_path = project_root / "data" / "traces" / "ftp_sessions.txt"
        if trace_path.exists():
            full_text = trace_path.read_text()
            sessions = full_text.split("---")
            for i, s in enumerate(sessions):
                s = s.strip()
                if s:
                    trace = SessionTrace(
                        project_id=project.id,
                        source_type="trace",
                        raw_content=s,
                    )
                    session.add(trace)
            print(f"Imported {len([s for s in sessions if s.strip()])} trace sessions")

        session.commit()
        print("Demo data import complete!")
        print(f"\nNext steps:")
        print(f"  1. Start backend: cd backend && uvicorn main:app --reload")
        print(f"  2. Run agents via API: POST /projects/{project.id}/run/full-pipeline")


if __name__ == "__main__":
    main()
