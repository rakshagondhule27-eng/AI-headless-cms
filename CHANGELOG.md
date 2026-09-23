# Changelog — V10 Final Submission

## V10.0.0

Final submission polish focused on reliability, governance, security and demonstration quality.

- Added system health endpoint with database and ML readiness checks.
- Added OpenAPI-style machine-readable API catalog.
- Expanded API documentation page with health/OpenAPI links.
- Added admin CSV analytics export.
- Added category API.
- Added security response headers and configurable secure session cookies.
- Hardened image uploads with extension and file-signature validation.
- Improved content governance: newly created content always starts as Draft.
- Editing Approved/Published/Pending Review content creates a Draft revision instead of silently changing reviewed content.
- Expanded version snapshots to preserve category, cover image and tags.
- Restoring a version returns the content to Draft and creates a new snapshot.
- Added publication-health visualization to Analytics.
- Added system-health strip to the Dashboard.
- Added favicon and improved metadata.
- Added final deployment/security/research documentation.
