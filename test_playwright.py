from playwright.sync_api import sync_playwright


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        page.set_content(
            "<html><title>Browser Test</title>"
            "<body>Hello BrowserGym</body></html>"
        )

        print("Title:", page.title())
        print("Text:", page.locator("body").inner_text())

        browser.close()


if __name__ == "__main__":
    main()