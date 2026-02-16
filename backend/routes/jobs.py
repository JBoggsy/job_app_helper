from flask import Blueprint, jsonify, request

from backend.database import db
from backend.models.job import Job

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@jobs_bp.route("", methods=["GET"])
def list_jobs():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return jsonify([job.to_dict() for job in jobs])


@jobs_bp.route("", methods=["POST"])
def create_job():
    data = request.get_json()
    job = Job(
        company=data["company"],
        title=data["title"],
        url=data.get("url"),
        status=data.get("status", "saved"),
        notes=data.get("notes"),
    )
    db.session.add(job)
    db.session.commit()
    return jsonify(job.to_dict()), 201


@jobs_bp.route("/<int:job_id>", methods=["GET"])
def get_job(job_id):
    job = db.get_or_404(Job, job_id)
    return jsonify(job.to_dict())


@jobs_bp.route("/<int:job_id>", methods=["PATCH"])
def update_job(job_id):
    job = db.get_or_404(Job, job_id)
    data = request.get_json()
    for field in ("company", "title", "url", "status", "notes"):
        if field in data:
            setattr(job, field, data[field])
    db.session.commit()
    return jsonify(job.to_dict())


@jobs_bp.route("/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    job = db.get_or_404(Job, job_id)
    db.session.delete(job)
    db.session.commit()
    return "", 204
