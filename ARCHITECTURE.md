# System Architecture

```text
                    USER / ADMIN / EDITOR / AUTHOR
                                |
                                v
                  +---------------------------+
                  | HTML / CSS / JavaScript   |
                  | Responsive Web Interface  |
                  +-------------+-------------+
                                |
                                v
                  +---------------------------+
                  |       Python Flask        |
                  | REST API + Auth + RBAC    |
                  | CRUD + Workflow + Upload  |
                  +------+--------------+-----+
                         |              |
              +----------+              +-----------+
              v                                      v
      +---------------+                      +----------------+
      | SQLite / SQL  |                      | AI / ML Engine |
      | SQLAlchemy    |                      | NLP + TF-IDF   |
      | Content       |                      | Classification |
      | Versions      |                      | Similarity     |
      | Audit         |                      +----------------+
      +-------+-------+
              |
              v
      +----------------+
      | Published REST |
      | API / JSON     |
      +--------+-------+
               |
       +-------+--------+
       |                |
       v                v
    Website         Mobile / Future Client
```

## Headless principle
The content repository and business logic do not depend on one presentation layer. Published content can be requested through REST APIs and consumed by other clients.

## AI principle
The AI layer is assistive. Generation, classification, summarization and quality analysis support users, while authorized users retain control over approval and publication.
