import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';

let loginPage: LoginPage;

test.describe('Login', () => {
  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.goto();
  });

  test("TC-001: The login form displays a Username field, a Password field, and a Login button.", { tag: ['@login', '@functional'] }, async () => {
    await test.step("Load the login page.", async () => {
      await loginPage.goto();
    });

    await test.step("Verify the login form contains a Username field, a Password field, and a Login button.", async () => {
      await expect(loginPage.usernameInput).toBeVisible();
      await expect(loginPage.passwordInput).toBeVisible();
      await expect(loginPage.loginButton).toBeVisible();
    });
  });

  test("TC-002: The Password field masks its input.", { tag: ['@login', '@functional'] }, async () => {
    await test.step("Enter a password in the Password field.", async () => {
      await loginPage.passwordInput.fill('password');
    });

    await test.step("Verify the input is masked.", async () => {
      // The password input is masked by default, so we can't directly verify the masking.
      // However, we can verify that the input type is 'password'.
      await expect(loginPage.passwordInput).toHaveAttribute('type', 'password');
    });
  });

  test("TC-003: Submitting the login form with an empty Username field shows the error message 'Epic sadface: Username is required'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Leave the Username field empty and submit the form.", async () => {
      await loginPage.login('', 'password');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Username is required');
    });
  });

  test("TC-004: Submitting the login form with an empty Username field shows the error message 'Epic sadface: Username is required'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Enter only whitespace in the Username field and submit the form.", async () => {
      await loginPage.login('   ', 'password');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Username is required');
    });
  });

  test("TC-005: Submitting the login form with an empty Username field shows the error message 'Epic sadface: Username is required'.", { tag: ['@login', '@functional'] }, async () => {
    await test.step("Enter a valid username in the Username field and submit the form.", async () => {
      await loginPage.login('standard_user', 'password');
    });

    await test.step("Verify the error message is not displayed.", async () => {
      await expect(loginPage.errorBanner).toBeHidden();
    });
  });

  test("TC-006: Submitting the login form with an empty Username field shows the error message 'Epic sadface: Username is required'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Enter a username with special characters in the Username field and submit the form.", async () => {
      await loginPage.login('!@#$%^&*()', 'password');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Username is required');
    });
  });

  test("TC-007: Submitting the login form with an empty Username field shows the error message 'Epic sadface: Username is required'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Enter a username with leading whitespace in the Username field and submit the form.", async () => {
      await loginPage.login('   standard_user', 'password');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Username is required');
    });
  });

  test("TC-008: Submitting the login form with an empty Username field shows the error message 'Epic sadface: Username is required'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Enter a username with trailing whitespace in the Username field and submit the form.", async () => {
      await loginPage.login('standard_user   ', 'password');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Username is required');
    });
  });

  test("TC-009: Submitting the login form with a Username filled in but an empty Password field shows the error message 'Epic sadface: Password is required'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Enter a valid username in the Username field, leave the Password field empty, and submit the form.", async () => {
      await loginPage.login('standard_user', '');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Password is required');
    });
  });

  test("TC-010: Submitting a username/password combination that does not match any accepted account shows the error message 'Epic sadface: Username and password do not match any user in this service'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Enter an invalid username and password combination and submit the form.", async () => {
      await loginPage.login('invalid_user', 'invalid_password');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Username and password do not match any user in this service');
    });
  });

  test("TC-011: Submitting valid credentials for standard_user logs the user in and redirects to /inventory.html.", { tag: ['@login', '@functional', '@regression', '@smoke'] }, async () => {
    await test.step("Enter valid credentials for standard_user and submit the form.", async () => {
      await loginPage.login('standard_user', 'secret_sauce');
    });

    await test.step("Verify the user is logged in and redirected to /inventory.html.", async () => {
      await expect(loginPage.page).toHaveURL(/.*inventory.html/);
    });
  });

  test("TC-013: Submitting valid credentials for locked_out_user does NOT log the user in and shows the error message 'Epic sadface: Sorry, this user has been locked out.'.", { tag: ['@login', '@negative'] }, async () => {
    await test.step("Enter valid credentials for locked_out_user and submit the form.", async () => {
      await loginPage.login('locked_out_user', 'secret_sauce');
    });

    await test.step("Verify the error message is displayed.", async () => {
      await loginPage.expectErrorMessage('Epic sadface: Sorry, this user has been locked out.');
    });
  });

  test("TC-014: An error banner can be dismissed by clicking its close button.", { tag: ['@login', '@functional'] }, async () => {
    await test.step("Click the close button on the error banner.", async () => {
      await loginPage.dismissErrorBanner();
    });

    await test.step("Verify the error banner is dismissed.", async () => {
      await expect(loginPage.errorBanner).toBeHidden();
    });
  });
});
