import { Page, Locator, expect } from '@playwright/test';
// Locators are grounded (real element identifiers) as per the provided source document.
export class ProductsPage {
  readonly page: Page;
  readonly pageTitle: Locator;
  readonly inventoryItems: Locator;
  readonly productName: Locator;
  readonly productPrice: Locator;
  readonly addToCartButton: Locator;
  readonly cartIcon: Locator;
  readonly cartBadgeCount: Locator;

  constructor(page: Page) {
    this.page = page;
    this.pageTitle = page.getByRole('heading', { name: 'Products' });
    this.inventoryItems = page.getByTestId('inventory-item');
    this.productName = page.getByTestId('product-name');
    this.productPrice = page.getByTestId('product-price');
    this.addToCartButton = page.getByRole('button', { name: 'Add to cart' });
    this.cartIcon = page.getByRole('link', { name: 'Cart' });
    this.cartBadgeCount = page.getByTestId('cart-badge-count');
  }

  async goto(): Promise<void> {
    await this.page.goto('https://www.saucedemo.com/inventory.html');
  }

  async expectPageTitle(): Promise<void> {
    await expect(this.pageTitle).toBeVisible();
  }

  async expectInventoryItemDetails(): Promise<void> {
    await expect(this.productName).toBeVisible();
    await expect(this.productPrice).toBeVisible();
    await expect(this.addToCartButton).toBeVisible();
  }

  async clickAddToCart(): Promise<void> {
    await this.addToCartButton.click();
  }

  async expectCartBadgeCount(count: number): Promise<void> {
    await expect(this.cartBadgeCount).toContainText(String(count));
  }
}