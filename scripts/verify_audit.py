from app import create_app, db
from app.models import AuditLog, User, Product, Sale
from app.services.audit_service import AuditService

app = create_app()

with app.app_context():
    print(f"Total Audit Logs: {AuditLog.query.count()}")
    
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5).all()
    if logs:
        print("\nRecent Logs:")
        for log in logs:
            print(f"- [{log.created_at}] {log.action} by User {log.user_id}: {log.details}")
    else:
        print("No audit logs found yet.")
