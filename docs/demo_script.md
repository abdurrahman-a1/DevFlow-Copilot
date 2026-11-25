flowchart TD
    A[1. Submit Client Text / Screenshot] --> B[2. Persist Raw InputDocument]
    B --> C[3. Extract Image Evidence & Normalize Context]
    C --> D[4. Generate Structured Spec & Engineering Artifacts]
    D --> E[5. Validate JSON Schema & Surface Open Questions]
    E --> F{6. Human Review Gate}
    F -->|Approve / Edit| G[7. Export Approved Markdown & JSON]
    F -->|Reject + Feedback| H[8. Regenerate New Run with Reviewer Note]
    H --> E