"""JobDocument model — versioned per-job documents (cover letters, resumes)."""

from backend.database import db


class JobDocument(db.Model):
    __tablename__ = "job_documents"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type = db.Column(db.String(50), nullable=False)  # "cover_letter", "resume"
    content = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    edit_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    job = db.relationship(
        "Job",
        backref=db.backref(
            "documents", cascade="all, delete-orphan", lazy="dynamic",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "doc_type": self.doc_type,
            "content": self.content,
            "version": self.version,
            "edit_summary": self.edit_summary,
            "created_at": (
                (self.created_at.isoformat() + "+00:00") if self.created_at else None
            ),
        }

    @classmethod
    def get_latest(cls, job_id, doc_type):
        """Get the latest version of a document for a job."""
        return (
            cls.query.filter_by(job_id=job_id, doc_type=doc_type)
            .order_by(cls.version.desc())
            .first()
        )

    @classmethod
    def get_history(cls, job_id, doc_type):
        """Get all versions of a document for a job, newest first."""
        return (
            cls.query.filter_by(job_id=job_id, doc_type=doc_type)
            .order_by(cls.version.desc())
            .all()
        )

    @classmethod
    def next_version(cls, job_id, doc_type):
        """Return the next version number for this job+doc_type pair."""
        latest = cls.get_latest(job_id, doc_type)
        return (latest.version + 1) if latest else 1
