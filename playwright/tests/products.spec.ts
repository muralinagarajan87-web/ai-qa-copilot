import { test } from '@playwright/test';
import { ProductsPage } from '../pages/ProductsPage';

let productsPage: ProductsPage;

test.describe('Products', () => {
  test.beforeEach(async ({ page }) => {
    productsPage = new ProductsPage(page);
    await productsPage.goto();
  });

  test("TC-012: The Products page displays the page title 'Products'.", { tag: ['@products', '@functional'] }, async () => {
    await test.step("Load the Products page.", async () => {
      await productsPage.goto();
    });

    await test.step("Verify the page title.", async () => {
      await productsPage.expectPageTitle();
    });
  });

  test("TC-015: Each inventory item on the Products page displays a product name, a price, and an 'Add to cart' button.", { tag: ['@products', '@functional'] }, async () => {
    await test.step("Load the Products page.", async () => {
      await productsPage.goto();
    });

    await test.step("Verify each inventory item details.", async () => {
      await productsPage.expectInventoryItemDetails();
    });
  });

  test("TC-016: Clicking 'Add to cart' on a product increases the shopping cart badge count shown on the cart icon by one.", { tag: ['@products', '@functional'] }, async () => {
    await test.step("Click the 'Add to cart' button on a product.", async () => {
      await productsPage.clickAddToCart();
    });

    await test.step("Verify the shopping cart badge count increases by one.", async () => {
      await productsPage.expectCartBadgeCount(1);
    });
  });
});