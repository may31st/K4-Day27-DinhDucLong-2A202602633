### Automated review (confidence 70%)

This PR introduces a new 'priority' field to tasks in a task tracking application, allowing tasks to be categorized as normal, high, or urgent. It modifies the command-line interface to accept a priority argument when adding tasks, updates the task model to include priority, and adjusts the storage layer to handle the new field in the database schema.

- **[issue]** `tasktrack/cli.py:8` — Consider adding validation for the priority argument to ensure it is within the expected range (0-2). Currently, any integer can be passed, which could lead to unexpected behavior.
- **[suggestion]** `tasktrack/models.py:7` — Add a comment or docstring to the Task class to explain the purpose of the priority field and its valid values.
- **[issue]** `tasktrack/storage.py:11` — The database schema change requires a migration plan. Ensure that existing users can upgrade without losing data or encountering errors.
- **[suggestion]** `tasktrack/storage.py:20` — Consider adding a check to ensure that the priority value is within the expected range before inserting it into the database.

_Reviewer note: Lab verification: authorize publishing this proposed review; unresolved migration and validation findings remain._