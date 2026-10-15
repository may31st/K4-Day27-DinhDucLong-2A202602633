### Automated review (confidence 85%)

This pull request adds a priority field to tasks in the task tracking application, allowing users to specify the priority level (normal, high, urgent) when adding tasks and displaying this priority in the task list.

- **[suggestion]** `tasktrack/cli.py:8` — Consider adding validation for the priority argument to ensure it only accepts values 0, 1, or 2.
- **[issue]** `tasktrack/models.py:7` — Ensure that the priority field is properly initialized and handled in all relevant methods to avoid potential NoneType errors.
- **[blocker]** `tasktrack/storage.py:10` — The database schema change requires a migration strategy for existing users to avoid data loss.
- **[nit]** `tasktrack/storage.py:15` — Consider adding a comment to explain the purpose of the priority field in the database schema.