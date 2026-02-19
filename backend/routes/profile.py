from flask import Blueprint, request

from backend.agent.user_profile import (
    read_profile,
    read_profile_raw,
    write_profile,
    ensure_profile_exists,
    is_onboarded,
    set_onboarded,
    get_onboarding_state,
    set_onboarding_in_progress,
)

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@profile_bp.route("", methods=["GET"])
def get_profile():
    ensure_profile_exists()
    content = read_profile()
    return {"content": content}


@profile_bp.route("", methods=["PUT"])
def update_profile():
    data = request.get_json()
    if not data or "content" not in data:
        return {"error": "content is required"}, 400
    write_profile(data["content"])
    return {"content": read_profile()}


@profile_bp.route("/onboarding-status", methods=["GET"])
def onboarding_status():
    ensure_profile_exists()
    return {"onboarded": is_onboarded(), "onboarding_state": get_onboarding_state()}


@profile_bp.route("/onboarding-status", methods=["POST"])
def update_onboarding_status():
    data = request.get_json()
    if data and "onboarded" in data:
        set_onboarded(bool(data["onboarded"]))
    return {"onboarded": is_onboarded(), "onboarding_state": get_onboarding_state()}
