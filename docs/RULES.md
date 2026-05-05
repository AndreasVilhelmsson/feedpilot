Iterate in small chunks (VERY important)
Explain:
- Why this pattern?
- What could go wrong?
- How would a senior improve this?

AI must be controlled by code, not prompts.
- Prompts can guide the model, but code must enforce product rules.
- Validate AI output with schemas before using it.
- Code decides allowed fields, enum values, scoring, state changes, persistence, and fallback behavior.
- Never treat prompt text as a safety boundary.

Write unit tests for this service before implementation
Implement code to pass tests
- Use TypeScript strictly
- No any types
- Use Axios for API calls
- Follow folder structure /features/*

Context:
- What I expected
- What happened
- Logs
- Code
