from backend.database import db


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500))
    status = db.Column(db.String(50), default="saved")
    notes = db.Column(db.Text)
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    location = db.Column(db.String(200))
    remote_type = db.Column(db.String(50))
    tags = db.Column(db.Text)
    contact_name = db.Column(db.String(200))
    contact_email = db.Column(db.String(200))
    applied_date = db.Column(db.Date)
    source = db.Column(db.String(200))
    job_fit = db.Column(db.Integer)
    requirements = db.Column(db.Text)
    nice_to_haves = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "company": self.company,
            "title": self.title,
            "url": self.url,
            "status": self.status,
            "notes": self.notes,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "location": self.location,
            "remote_type": self.remote_type,
            "tags": self.tags,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "applied_date": self.applied_date.isoformat() if self.applied_date else None,
            "source": self.source,
            "job_fit": self.job_fit,
            "requirements": self.requirements,
            "nice_to_haves": self.nice_to_haves,
            "created_at": (self.created_at.isoformat() + "+00:00") if self.created_at else None,
            "updated_at": (self.updated_at.isoformat() + "+00:00") if self.updated_at else None,
        }
