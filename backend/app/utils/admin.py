from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.user import User


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user = User.query.filter_by(id=int(get_jwt_identity())).first()
        if user is None:
            return jsonify({"error": "User not found."}), 404
        if not user.is_admin:
            return jsonify({"error": "Admin access required."}), 403
        return fn(*args, **kwargs)

    return wrapper