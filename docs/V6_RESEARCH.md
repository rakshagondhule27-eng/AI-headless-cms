# V6 Research Upgrade

## Research contribution
V6 adds a human-in-the-loop governance layer around AI-assisted content generation and ML classification. The system explicitly separates AI assistance from final publication decisions.

## Workflow experiment idea
Measure how many items move through Draft → Pending Review → Approved/Rejected → Published, and record review latency using audit timestamps.

## Evaluation
- ML: accuracy, precision, recall, F1, confusion matrix
- Search: relevance of returned content
- API: correctness and response time
- Database: query/index performance
- Governance: approval rate, rejection rate, review latency
- AI quality: human rating of usefulness and correctness

## Limitation
The current implementation is still a student research prototype. SQLite is appropriate for local demonstration; PostgreSQL/Docker/deployment can be used for production-style evaluation. The demonstration dataset must not be presented as a general benchmark.
