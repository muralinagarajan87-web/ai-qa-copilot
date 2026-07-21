import { Page, Locator, expect } from '@playwright/test';
// Locators are grounded (real element identifiers) as per the provided source document.
export class LoginPage {
  readonly page: Page;
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly loginButton: Locator;
  readonly errorBanner: Locator;
  readonly errorBannerCloseButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.usernameInput = page.getByTestId('username');
    this.passwordInput = page.getByTestId('password');
    this.loginButton = page.getByTestId('login-button');
    this.errorBanner = page.getByTestId('error');
    this.errorBannerCloseButton = page.getByTestId('error-button');
  }

  async goto(): Promise<void> {
    await this.page.goto('https://www.saucedemo.com/');
  }

  async login(username: string, password: string): Promise<void> {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
  }

  async expectErrorMessage(message: string): Promise<void> {
    await expect(this.errorBanner).toContainText(message);
  }

  async dismissErrorBanner(): Promise<void> {
    await this.errorBannerCloseButton.click();
  }
}