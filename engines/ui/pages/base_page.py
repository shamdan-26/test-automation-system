from __future__ import annotations

from playwright.sync_api import Page


class BasePage:
    """Page Object Model base — all pages inherit from this."""

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    def navigate(self, path: str = "") -> None:
        self.page.goto(self.base_url + path)

    def wait_for_load(self) -> None:
        self.page.wait_for_load_state("networkidle")

    def get_text(self, selector: str) -> str:
        return self.page.locator(selector).inner_text()

    def click(self, selector: str) -> None:
        self.page.locator(selector).click()

    def fill(self, selector: str, value: str) -> None:
        self.page.locator(selector).fill(value)

    def is_visible(self, selector: str) -> bool:
        return self.page.locator(selector).is_visible()

    def screenshot(self, name: str, output_dir: str = "outputs/artifacts") -> str:
        path = f"{output_dir}/{name}.png"
        self.page.screenshot(path=path, full_page=True)
        return path
