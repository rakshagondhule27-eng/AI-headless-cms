# Security Notes

This is a final-year academic project and local demonstration application, not a production SaaS security claim.

Implemented safeguards:

- Passwords are stored as Werkzeug password hashes.
- Session cookies use HttpOnly and SameSite=Lax; Secure can be enabled with `SESSION_COOKIE_SECURE=1` behind HTTPS.
- Security response headers are applied by the Flask application.
- Admin-only actions protect deletion, audit logs and analytics export.
- Role checks protect approval and publication.
- Uploaded filenames are sanitized with `secure_filename`.
- Upload extensions and basic file signatures are validated.
- Upload size is limited to 5 MB.
- Public API exposes published content only.
- SQLAlchemy parameterization is used for database queries.

Before real deployment, additionally configure a strong `SECRET_KEY`, HTTPS, CSRF protection, rate limiting, centralized logging, stronger media scanning and a production database.
