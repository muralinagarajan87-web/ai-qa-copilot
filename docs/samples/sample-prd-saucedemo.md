# Feature: Swag Labs (SauceDemo) Login and Product Listing

## Summary

Users log into the Swag Labs demo e-commerce application and, on success, land on a Products page where they can add items to a shopping cart. This PRD describes the actual, currently-live behavior of the public QA practice application at https://www.saucedemo.com/, verified directly against the live site rather than assumed.

## Application Under Test

- URL: `https://www.saucedemo.com/`
- Login form fields:
  - Username: `<input id="user-name" data-test="username">`
  - Password: `<input id="password" data-test="password" type="password">` (masked input)
  - Login button: `<input id="login-button" data-test="login-button" type="submit">`
- Accepted usernames (all use the password `secret_sauce`): `standard_user`, `locked_out_user`, `problem_user`, `performance_glitch_user`, `error_user`, `visual_user`
- Error banner: `<h3 data-test="error">` containing the message text, with a dismiss button `<button data-test="error-button">`

## Requirements

1. The login form displays a Username field, a Password field, and a Login button.
2. The Password field masks its input (type="password").
3. Submitting the login form with an empty Username field shows the error message "Epic sadface: Username is required".
4. Submitting the login form with a Username filled in but an empty Password field shows the error message "Epic sadface: Password is required".
5. Submitting a username/password combination that does not match any accepted account shows the error message "Epic sadface: Username and password do not match any user in this service".
6. Submitting valid credentials for `standard_user` (password `secret_sauce`) logs the user in and redirects to `/inventory.html`, which displays the page title "Products".
7. Submitting valid credentials for `locked_out_user` (password `secret_sauce`) does NOT log the user in, even though the password is correct, and shows the error message "Epic sadface: Sorry, this user has been locked out."
8. An error banner can be dismissed by clicking its close ("X") button, after which the error message is no longer visible on the page.
9. On the Products page, each inventory item displays a product name, a price, and an "Add to cart" button.
10. Clicking "Add to cart" on a product increases the shopping cart badge count shown on the cart icon by one.

## Out of Scope

- `problem_user`, `performance_glitch_user`, `error_user`, and `visual_user` -- these accounts log in successfully but exhibit visual/rendering quirks (broken images, artificial slowness, JS errors, layout shifts) that are not reliably verifiable via functional assertions and are excluded from this PRD.
- Checkout flow beyond adding an item to the cart.
- Password reset or account creation -- not available on this application.
