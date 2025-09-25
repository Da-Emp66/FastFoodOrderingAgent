from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Set up Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run browser in headless mode
chrome_options.add_argument("--disable-gpu")  # Disable GPU for compatibility
chrome_options.add_argument("--window-size=1920,1080")  # Set window size

# Path to your ChromeDriver
service = Service(ChromeDriverManager().install())

# Initialize the WebDriver
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    # Open the webpage
    driver.get("https://google.com")

    # Save a screenshot of the rendered page
    driver.save_screenshot("screenshot.png")
    print("Screenshot saved as 'screenshot.png'")
finally:
    # Close the browser
    driver.quit()
    