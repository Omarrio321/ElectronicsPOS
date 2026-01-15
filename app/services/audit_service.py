from app import db
from app.models import AuditLog
from flask import request
from flask_login import current_user
import json

class AuditService:
    @staticmethod
    def log_action(action, target_type=None, target_id=None, details=None):
        """
        Log an audit event.
        
        Args:
            action (str): The action performed (e.g., 'LOGIN', 'CREATE', 'UPDATE').
            target_type (str, optional): The type of entity affected (e.g., 'User', 'Product').
            target_id (str, optional): The ID of the entity affected.
            details (dict, optional): Additional structured details about the event.
        """
        try:
            user_id = current_user.id if current_user.is_authenticated else None
            ip_address = request.remote_addr if request else None
            user_agent = request.user_agent.string if request and request.user_agent else None
            
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=str(target_id) if target_id else None,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # Fallback logger if DB logging fails
            # In a real production system, this should go to a file logger or Sentry
            print(f"Failed to create audit log: {e}")
            db.session.rollback()

    @staticmethod
    def get_logs(page=1, per_page=20):
        """Retrieve paginated audit logs"""
        return AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page)
