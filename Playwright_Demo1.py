from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def main():
    query = "best places to visit in sydney"

    with sync_playwright() as p:
        # Launch browser with a common Windows/Chrome User Agent
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
        )
        page = context.new_page()

        # Step 1: Go to Bing and wait until the DOM is fully constructed
        print("1. Navigating to Bing...")
        page.goto("https://www.bing.com", wait_until="domcontentloaded", timeout=60000)

        # Use Playwright CSS selector to target the ID: 'input#sb_form_q'
        search_input_locator = page.locator('input#sb_form_q')

        # Step 2: Try to dismiss consent (best-effort)
        print("2. Checking for consent banner...")
        
        # We try to click a generic 'Accept' or 'Agree' button for the consent banner
        try:
            page.get_by_text("Accept").click(timeout=3000)
            print("   -> Accepted consent banner (or similar).")
        except PlaywrightTimeoutError:
             try:
                 page.get_by_role("button", name="Agree").click(timeout=1000)
                 print("   -> Agreed to consent banner (or similar).")
             except PlaywrightTimeoutError:
                 print("   -> No visible consent banner found or it was auto-dismissed.")
                 pass 

        # Step 3: Wait for the search box to be visible
        print("3. Waiting for search box visibility...")
        try:
            # Wait for the locator to be ready for action. The state must be one of (attached|detached|visible|hidden).
            search_input_locator.wait_for(state="visible", timeout=20000)
            print("   -> Search box is visible.")
            
            # 💡 NOTE: The line search_input_locator.wait_for(state="enabled", timeout=5000) 
            # has been REMOVED to fix the 'state: expected one of...' error. 
            # The .fill() action below automatically waits for the element to be enabled.

        except PlaywrightTimeoutError:
            page.screenshot(path="bing_no_input_id.png", full_page=True)
            raise RuntimeError(
                "Search input with ID 'sb_form_q' not visible/ready. Screenshot: bing_no_input_id.png"
            )

        # Step 4: Perform the search
        print(f"4. Performing search for: '{query}'")
        # .fill() automatically waits for the locator to be visible and enabled.
        search_input_locator.fill(query)
        search_input_locator.press("Enter")
        print("   -> Search initiated.")

        # Step 5: Wait for results
        # Locator for search result link (remains the same)
        results_link_locator = page.locator('//li[contains(@class,"b_algo")]//h2/a')
        
        print("5. Waiting for search results...")
        try:
            # Wait until the first result link is visible
            results_link_locator.first.wait_for(state="visible", timeout=30000)
        except PlaywrightTimeoutError:
            print("   -> Timed out waiting for search results.")
            browser.close()
            return
            

        # Step 6: Extract top 3
        print("6. Extracting results...")
        results = []
        links_count = results_link_locator.count()

        for i in range(min(links_count, 10)):
            link_element = results_link_locator.nth(i)
            if link_element.is_visible(): 
                title = link_element.inner_text().strip()
                url = link_element.get_attribute("href")

                # Basic validation
                if title and url and url.startswith("http"):
                    results.append((title, url))

            if len(results) == 3:
                break

        print("\n🏆 Top 3 results:")
        for i, (title, url) in enumerate(results, 1):
            print(f"{i}. {title}\n   🔗 {url}\n")
        
        browser.close()


if __name__ == "__main__":
    main()