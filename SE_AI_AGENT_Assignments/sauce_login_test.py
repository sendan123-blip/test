from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time

# --- Configuration ---
TEST_URL = "https://www.saucedemo.com/"
WAIT_TIME = 10  # Maximum seconds to wait for an element

def run_sauce_login_test():
    print("--- Starting SauceDemo Login Test ---")
    
    # 1. Initialize the WebDriver (Chrome is assumed)
    # This line uses the standard webdriver import which should resolve the error.
    try:
        # Note: In modern Selenium, no arguments are needed for Chrome() if it's installed.
        driver = webdriver.Chrome()
    except Exception as e:
        print(f"Error initializing Chrome driver. Please ensure Chrome is installed and updated: {e}")
        return

    try:
        # 2. Open the Test Page
        driver.get(TEST_URL)
        print(f"Navigated to: {TEST_URL}")
        
        # Set window size for standard view (optional, but good practice)
        driver.set_window_size(1280, 800)

        # 3. Define Locators
        USERNAME_FIELD = (By.ID, "user-name")
        PASSWORD_FIELD = (By.ID, "password")
        LOGIN_BUTTON = (By.ID, "login-button")
        
        # Locator for verification (An element only visible AFTER successful login)
        PRODUCTS_HEADER = (By.XPATH, "//span[text()='Products']") # 

        # 4. Use WebDriverWait for Stable Interaction
        wait = WebDriverWait(driver, WAIT_TIME)

        # --- Login Steps ---
        
        # A. Wait for and enter Username
        print("Entering Username...")
        user_input = wait.until(EC.presence_of_element_located(USERNAME_FIELD))
        user_input.send_keys("standard_user")

        # B. Wait for and enter Password
        print("Entering Password...")
        pass_input = wait.until(EC.presence_of_element_located(PASSWORD_FIELD))
        pass_input.send_keys("secret_sauce")

        # C. Click Login Button
        print("Clicking Login...")
        login_btn = wait.until(EC.element_to_be_clickable(LOGIN_BUTTON))
        login_btn.click()

        # 5. Verification: Wait for the expected element on the products page
        print("Verifying successful login...")
        
        wait.until(EC.presence_of_element_located(PRODUCTS_HEADER))
        
        # Final Success Message
        print("\n✅ SUCCESS: Login was successful!")
        print(f"Current URL: {driver.current_url}")
        
        # Optional: Keep the browser open briefly for visual confirmation
        time.sleep(3)

    except TimeoutException:
        print("\n❌ FAILURE: Test failed due to element timeout.")
        print("Could not find the 'Products' header after login.")
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: An unexpected error occurred: {e}")

    finally:
        # 6. Clean Up
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    # If the error persists, you should run this command in your terminal:
    # pip install --upgrade selenium
    # This ensures your installed package is not corrupted.
    run_sauce_login_test()