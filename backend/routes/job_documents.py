"""Job documents blueprint — versioned cover letters and resumes per job."""

import logging

from flask import Blueprint, jsonify, request

from backend.database import db
from backend.models.job import Job
from backend.models.job_document import JobDocument

logger = logging.getLogger(__name__)

job_documents_bp = Blueprint(
    "job_documents", __name__, url_prefix="/api/jobs",
)


@job_documents_bp.route("/<int:job_id>/documents", methods=["GET"])
def get_latest_document(job_id):
    """Get the latest version of a document.  Requires ``?type=`` query param."""
    db.get_or_404(Job, job_id)
    doc_type = request.args.get("type")
    if not doc_type:
        return jsonify({"error": "type query parameter is required"}), 400
    doc = JobDocument.get_latest(job_id, doc_type)
    if not doc:
        return '', 204
    return jsonify(doc.to_dict())


@job_documents_bp.route("/<int:job_id>/documents/history", methods=["GET"])
def get_document_history(job_id):
    """Get all versions of a document.  Requires ``?type=`` query param."""
    db.get_or_404(Job, job_id)
    doc_type = request.args.get("type")
    if not doc_type:
        return jsonify({"error": "type query parameter is required"}), 400
    docs = JobDocument.get_history(job_id, doc_type)
    return jsonify([d.to_dict() for d in docs])


@job_documents_bp.route("/<int:job_id>/documents", methods=["POST"])
def save_document(job_id):
    """Save a new version of a document."""
    db.get_or_404(Job, job_id)
    data = request.get_json()
    doc_type = data.get("doc_type")
    content = data.get("content")
    if not doc_type:
        return jsonify({"error": "doc_type is required"}), 400
    if not content:
        return jsonify({"error": "content is required"}), 400

    doc = JobDocument(
        job_id=job_id,
        doc_type=doc_type,
        content=content,
        version=JobDocument.next_version(job_id, doc_type),
        edit_summary=data.get("edit_summary"),
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify(doc.to_dict()), 201


@job_documents_bp.route(
    "/<int:job_id>/documents/<int:doc_id>", methods=["DELETE"],
)
def delete_document(job_id, doc_id):
    """Delete a specific document version."""
    db.get_or_404(Job, job_id)
    doc = db.get_or_404(JobDocument, doc_id)
    if doc.job_id != job_id:
        return jsonify({"error": "Document does not belong to this job"}), 404
    db.session.delete(doc)
    db.session.commit()
    return "", 204
