from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)


def register_jwt_handlers(jwt, db, TokenBlocklist):
    @jwt.token_in_blocklist_loader
    def is_token_revoked(_jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        if not jti:
            return True
        return db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar() is not None

    @jwt.unauthorized_loader
    def jwt_missing_token_callback(reason):
        return jsonify({"error": "Authentication required", "detail": reason}), 401

    @jwt.invalid_token_loader
    def jwt_invalid_token_callback(reason):
        return jsonify({"error": "Invalid session", "detail": reason}), 401

    @jwt.expired_token_loader
    def jwt_expired_token_callback(_jwt_header, _jwt_payload):
        response = jsonify({"error": "Session expired"})
        unset_jwt_cookies(response)
        return response, 401

    @jwt.revoked_token_loader
    def jwt_revoked_token_callback(_jwt_header, _jwt_payload):
        response = jsonify({"error": "Session has been logged out"})
        unset_jwt_cookies(response)
        return response, 401


def get_user_from_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def get_legacy_authenticated_user(db, User):
    token = get_user_from_token()
    if not token:
        return None

    try:
        user_id = int(token)
    except (TypeError, ValueError):
        return None

    return db.session.get(User, user_id)


def get_authenticated_user(db, User):
    try:
        verify_jwt_in_request(optional=True, locations=["cookies", "headers"])
        identity = get_jwt_identity()
        if identity is not None:
            try:
                return db.session.get(User, int(identity))
            except (TypeError, ValueError):
                return None
    except Exception:
        pass

    return get_legacy_authenticated_user(db, User)


def require_admin_user(db, User):
    user = get_authenticated_user(db, User)
    if not user:
        return None, (jsonify({"error": "Authentication required"}), 401)

    if user.role != "admin":
        return None, (jsonify({"error": "Admin access required"}), 403)

    return user, None


def issue_login_response(app, user):
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role, "email": user.email},
    )
    response = jsonify(
        {
            "message": "Login successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role,
            },
            "session_expires_in_seconds": int(app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
        }
    )
    set_access_cookies(response, access_token)
    return response


def serialize_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
