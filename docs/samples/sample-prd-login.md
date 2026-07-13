# Feature: User Login

## Summary
Users must be able to log into the web application using their email address and password.

## Requirements
- The login form has two fields: Email and Password, and a "Log In" button.
- Email must be a valid email format; Password must be at least 8 characters.
- On successful login, the user is redirected to `/dashboard`.
- On invalid credentials, show the error message "Invalid email or password" without revealing which field was wrong.
- After 5 consecutive failed login attempts for the same account within 15 minutes, lock the account for 15 minutes and show "Account temporarily locked. Try again later."
- Password field must mask input by default, with a toggle to reveal it.
- A "Forgot password?" link navigates to the password reset flow (out of scope for this PRD).
- The Log In button is disabled while the request is in flight, to prevent duplicate submissions.
