from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time
import json
import random

class FaceScraperService:
    def  __init__(self, profile:str,db,cookie_file:str = "cookies.json"):
        self.profile_url = f"https://www.facebook.com/{profile}"
        self.cookie_file = cookie_file
        self.profile = profile
        self.driver = None
        self.actions = None
        self.db = db
        self.collection = db["Facebook"]

    def _setup_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=es-ES")
        options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64)...")

        self.driver = webdriver.Chrome(options=options)
        self.actions = ActionChains(self.driver)

    def _load_cookies(self):
        with open(self.cookie_file, "r") as f:
            cookies_list = json.load(f)

        self.driver.get("https://www.facebook.com/")
        time.sleep(random.uniform(5.0, 12.0))
        for cookie in cookies_list:
            cookie.pop("sameSite", None)
            self.driver.add_cookie(cookie)

    async def scrape_posts(self, max_posts:int = 30)-> list:
        self._setup_driver()
        self._load_cookies()
        self.driver.get(self.profile_url)
        time.sleep(random.uniform(5.0, 20.0))

        SCROLL_PAUSE_TIME = 3
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        post_data = []

        while len(post_data) < max_posts:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)

            try:
                ver_mas_buttons = self.driver.find_elements(By.XPATH, '//div[contains(text(), "Ver más")]')
                for btn in ver_mas_buttons:
                    try:
                        self.actions.move_to_element(btn).click().perform()
                        time.sleep(0.5)
                    except:
                        continue
            except:
                pass

            posts = self.driver.find_elements(By.XPATH, '//div[@data-ad-preview="message"]')

            for post in posts:
                try:
                    post_container = post.find_element(By.XPATH, "./ancestor::div[contains(@role,'article')]")
                    text = post.text.strip()

                    try:
                        fecha = post_container.find_element(By.XPATH, ".//abbr | .//a/span[contains(@aria-label, ' · ')]").get_attribute("aria-label")
                    except:
                        fecha = "Fecha no encontrada"

                    try:
                        reacciones = post_container.find_element(By.XPATH, ".//span[contains(@aria-label,'reacciones')]").get_attribute("aria-label")
                    except:
                        reacciones = "No disponible"

                    try:
                        engagement = post_container.find_element(By.XPATH, ".//span[contains(text(),'comentarios') or contains(text(),'veces compartido')]").text
                    except:
                        engagement = "No disponible"

                    post_data.append({
                        "profile":self.profile,
                        "texto": text,
                        "fecha": fecha,
                        "reacciones": reacciones,
                        "interacciones": engagement
                    })

                    if len(post_data) >= max_posts:
                        break
                except:
                    continue

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        self.driver.quit()
        if post_data:
            self.collection.insert_many(post_data)

        return post_data
        
