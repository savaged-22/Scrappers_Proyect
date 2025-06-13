import os
import time
import json
import random
import re
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from models import FacebookPost, MediaContent, EngagementMetrics, FacebookScrapeResult
from models.FacebookScrape import FacebookPost, MediaContent, EngagementMetrics, FacebookScrapeResult


# Configuración del logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FaceScraperService:
    def __init__(self, profile_id: str, db, cookie_file: str = "cookiesFC.json"):
        self.profile_id = profile_id
        self.profile_url = f"https://www.facebook.com/{profile_id}"
        
        # Get the directory of the current file (FaceScraperService.py)
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Go up one directory from 'services' to reach 'Scrappers_Proyect'
        # This will give: /home/kali/.tools/extract_Data/Scrappers_Proyect/
        project_root = os.path.abspath(os.path.join(current_file_dir, os.pardir))
        
        # Now, join the project_root with the cookie_file name
        # This should result in: /home/kali/.tools/extract_Data/Scrappers_Proyect/cookiesFC.json
        self.cookie_file_path = os.path.join(project_root, cookie_file)
        
        # *** IMPORTANT DEBUGGING STEP ***
        # Add this line to your code to confirm the path being used!
        logging.info(f"Looking for cookie file at: {self.cookie_file_path}")
        
        self.driver = None
        self.actions = None
        self.db = db
        self.posts_collection = db["facePosts"] 
        self.scrape_results_collection = db["facebook_scrapes"] 

    def _setup_driver(self):
        """Configura y retorna una instancia del driver de Chrome."""
        options = Options()
        # options.add_argument("--headless=new") # Descomentar para producción
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=es-ES")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.actions = ActionChains(self.driver)
            logging.info("WebDriver setup complete.")
        except WebDriverException as e:
            logging.error(f"Error setting up WebDriver: {e}. Make sure ChromeDriver is installed and in PATH.")
            raise

    def _load_cookies(self):
        """Carga las cookies desde un archivo JSON."""
        if not os.path.exists(self.cookie_file_path):
            logging.warning(f"Cookie file not found at {self.cookie_file_path}. Manual login may be required.")
            return False
        
        try:
            with open(self.cookie_file_path, "r") as f:
                cookies_list = json.load(f)
            
            self.driver.get("https://www.facebook.com/")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            for cookie in cookies_list:
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    cookie['sameSite'] = 'Lax'
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logging.warning(f"Could not add cookie: {cookie.get('name', 'N/A')}. Error: {e}")
            
            logging.info("Cookies loaded successfully.")
            return True
        except json.JSONDecodeError:
            logging.error(f"Error decoding cookies.json. File might be corrupted.")
            return False
        except Exception as e:
            logging.error(f"Error loading cookies: {e}")
            return False

    def _login_if_necessary(self):
        """
        Intenta cargar cookies y navega al perfil.
        Asume que si las cookies se cargan, la sesión es válida.
        """
        self.driver.get("https://www.facebook.com")
        time.sleep(random.uniform(5, 10))

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Inicio' and @role='link']"))
            )
            logging.info("Login appears successful based on cookie persistence.")
            return True
        except TimeoutException:
            logging.warning("Login verification failed. Cookies might be expired or invalid. Please ensure cookies.json is valid.")
            return False
        except Exception as e:
            logging.error(f"Error during login verification: {e}")
            return False

    def _extract_post_details(self, post_element) -> Optional[FacebookPost]:
        """
        Extrae los detalles de una publicación de Selenium WebDriver element
        y los mapea al modelo FacebookPost.
        """
        post_uuid = str(uuid.uuid4()) # Siempre generamos un UUID para el _id interno
        post_url = None
        post_text = None
        post_date = None
        post_type = "otro"
        media_content = []
        engagement_metrics_data = EngagementMetrics()
        
        try:
            # URL de la publicación (este es el campo clave para el upsert)
            link_element = None
            try:
                # El enlace al timestamp suele ser la URL de la publicación
                link_element = post_element.find_element(By.XPATH, ".//a[contains(@href, '/posts/') or contains(@href, '/videos/') or contains(@href, '/photos/')][contains(@aria-label, '·')]")
                post_url = link_element.get_attribute("href")
            except NoSuchElementException:
                logging.debug(f"Could not find primary URL link for post {post_uuid}. Trying fallback.")
                try:
                    # Fallback: buscar cualquier enlace que parezca llevar a la publicación
                    # Esto podría ser un enlace a una foto específica en un álbum
                    post_url_elem = post_element.find_element(By.XPATH, ".//a[contains(@href, '/fbid=') or contains(@href, '/photo.php?fbid=')]")
                    post_url = post_url_elem.get_attribute("href")
                except NoSuchElementException:
                    logging.warning(f"No direct URL found for post {post_uuid}. Skipping this post for individual storage.")
                    return None # Si no hay URL, no podemos hacer upsert reliable

            # Es crucial que post_url no sea None para el upsert
            if not post_url:
                logging.warning(f"Post URL could not be extracted for post (UUID: {post_uuid}). Skipping this post.")
                return None


            # Texto de la publicación
            try:
                text_element = post_element.find_element(By.XPATH, './/div[@data-ad-preview="message"]')
                post_text = text_element.text.strip()
            except NoSuchElementException:
                post_text = None

            # Fecha de publicación
            try:
                # Usar el link_element que ya se encontró para la URL, si existe.
                # Si link_element es None (porque no se encontró URL), esto fallará.
                # Asegurarse de que date_str se inicializa para el mensaje de log
                date_str = None
                if link_element:
                    date_str = link_element.get_attribute("aria-label")
                    post_date = self._parse_facebook_date(date_str)
                else:
                    raise NoSuchElementException("No link element found for date extraction.")
            except NoSuchElementException:
                logging.warning(f"Date element not found for post {post_uuid}.")
                post_date = datetime.utcnow() - timedelta(days=random.randint(1, 30))
            except Exception as e:
                logging.warning(f"Error parsing date for post {post_uuid}: {e}. Date string: '{date_str}'")
                post_date = datetime.utcnow() - timedelta(days=random.randint(1, 15))


            # Extraer contenido multimedia (imágenes y videos)
            try:
                # Intenta encontrar contenedores de imágenes/videos que suelen tener un atributo de rol o una clase distintiva
                # Estos XPATHs pueden necesitar ajuste fino y observación constante
                media_containers = post_element.find_elements(By.XPATH, ".//div[contains(@role, 'img')] | .//div[contains(@data-ft, 'media_set_id')]")

                for container in media_containers:
                    # Intentar encontrar imágenes dentro del contenedor
                    img_elements = container.find_elements(By.XPATH, ".//img[contains(@src, 'scontent')]")
                    for img in img_elements:
                        img_url = img.get_attribute("src")
                        if img_url and "scontent" in img_url:
                            media_content.append(MediaContent(
                                id_media=str(uuid.uuid4()),
                                tipo="imagen",
                                url=img_url,
                                descripcion=img.get_attribute("alt") or ""
                            ))
                            post_type = "foto" # Si al menos una imagen, es de foto

                    # Intentar encontrar videos dentro del contenedor
                    video_elements = container.find_elements(By.XPATH, ".//video[contains(@src, 'video') and not(@src='')]")
                    for vid in video_elements:
                        vid_url = vid.get_attribute("src")
                        if vid_url and "video" in vid_url:
                            media_content.append(MediaContent(
                                id_media=str(uuid.uuid4()),
                                tipo="video",
                                url=vid_url,
                                descripcion=vid.get_attribute("aria-label") or ""
                            ))
                            post_type = "video" # Si al menos un video, es de video
                            
                # Si no se encontraron contenedores específicos, buscar imágenes/videos directamente en el post_element
                if not media_content:
                    img_elements_direct = post_element.find_elements(By.XPATH, ".//img[contains(@src, 'scontent')]")
                    for img in img_elements_direct:
                        img_url = img.get_attribute("src")
                        # Filtra avatares, logos, etc.
                        if img_url and "scontent" in img_url and not re.search(r'profile_pic|avatar|logo', img_url):
                            media_content.append(MediaContent(
                                id_media=str(uuid.uuid4()),
                                tipo="imagen",
                                url=img_url,
                                descripcion=img.get_attribute("alt") or ""
                            ))
                            post_type = "foto"

                    video_elements_direct = post_element.find_elements(By.XPATH, ".//video[contains(@src, 'video') and not(@src='')]")
                    for vid in video_elements_direct:
                        vid_url = vid.get_attribute("src")
                        if vid_url and "video" in vid_url:
                            media_content.append(MediaContent(
                                id_media=str(uuid.uuid4()),
                                tipo="video",
                                url=vid_url,
                                descripcion=vid.get_attribute("aria-label") or ""
                            ))
                            post_type = "video"

            except Exception as e:
                logging.warning(f"Error extracting media for post {post_uuid}: {e}")

            # Extraer enlaces adjuntos
            enlace_adjunto = None
            titulo_enlace = None
            descripcion_enlace = None
            try:
                link_card = post_element.find_element(By.XPATH, ".//a[contains(@href, '/l.php?u=') and @role='link']")
                enlace_adjunto = link_card.get_attribute("href")
                
                try:
                    titulo_enlace_elem = link_card.find_element(By.XPATH, ".//span[contains(@class, 'x193iq5w') or contains(@class, 'x1c4mr0') or contains(@class, 'x1iorvi4')][1]")
                    titulo_enlace = titulo_enlace_elem.text.strip()
                except NoSuchElementException:
                    pass
                try:
                    desc_enlace_elem = link_card.find_element(By.XPATH, ".//span[contains(@class, 'x193iq5w') or contains(@class, 'x1c4mr0') or contains(@class, 'x1iorvi4')][2]")
                    descripcion_enlace = desc_enlace_elem.text.strip()
                except NoSuchElementException:
                    pass
                post_type = "enlace"

            except NoSuchElementException:
                pass
            except Exception as e:
                logging.warning(f"Error extracting linked content for post {post_uuid}: {e}")

            # Métricas de interacción
            try:
                reactions_elem = post_element.find_element(By.XPATH, ".//span[contains(@aria-label,'reacciones')]")
                reactions_text = reactions_elem.get_attribute("aria-label")
                engagement_metrics_data.reacciones_totales = self._parse_reactions_text(reactions_text)
            except NoSuchElementException:
                pass
            except Exception as e:
                logging.warning(f"Error extracting reactions for post {post_uuid}: {e}")

            try:
                engagement_elem = post_element.find_element(By.XPATH, ".//span[contains(text(),'comentarios') or contains(text(),'veces compartido') or contains(text(),'compartido')]")
                engagement_text = engagement_elem.text
                comms, shares = self._parse_engagement_text(engagement_text)
                engagement_metrics_data.comentarios_totales = comms
                engagement_metrics_data.compartidos_totales = shares
            except NoSuchElementException:
                pass
            except Exception as e:
                logging.warning(f"Error extracting comments/shares for post {post_uuid}: {e}")

            return FacebookPost(
                id_publicacion=post_uuid,
                url_publicacion=post_url, # ¡Es crucial que esta URL sea precisa para el upsert!
                id_pagina_o_usuario=self.profile_id,
                nombre_pagina_o_usuario=self.profile_id,
                fecha_publicacion=post_date,
                contenido_texto=post_text,
                tipo_publicacion=post_type,
                multimedia=media_content,
                enlace_adjunto=enlace_adjunto,
                titulo_enlace=titulo_enlace,
                descripcion_enlace=descripcion_enlace,
                engagement_metrics=engagement_metrics_data
            )
        except Exception as e:
            logging.error(f"Failed to extract details for a post element (UUID: {post_uuid}): {e}", exc_info=True)
            return None

    def _parse_facebook_date(self, date_str: str) -> datetime:
        """Intenta parsear varias cadenas de fecha de Facebook a objetos datetime."""
        if "hace" in date_str.lower():
            match = re.search(r'hace (\d+)\s*(minuto|minutos|hora|horas|día|días|semana|semanas|mes|meses|año|años)', date_str.lower())
            if match:
                value = int(match.group(1))
                unit = match.group(2)
                now = datetime.utcnow()
                if unit.startswith("minuto"): return now - timedelta(minutes=value)
                if unit.startswith("hora"): return now - timedelta(hours=value)
                if unit.startswith("día"): return now - timedelta(days=value)
                if unit.startswith("semana"): return now - timedelta(weeks=value)
                if unit.startswith("mes"): return now - timedelta(days=value * 30)
                if unit.startswith("año"): return now - timedelta(days=value * 365)
        
        logging.warning(f"Could not precisely parse date string: '{date_str}'. Returning current time minus random days.")
        return datetime.utcnow() - timedelta(days=random.randint(1, 15))

    def _parse_reactions_text(self, text: str) -> int:
        """Extrae el número total de reacciones de la cadena aria-label."""
        total = 0
        text = text.replace('.', '').replace(',', '')
        match = re.search(r'(\d+) (reacción|reacciones|persona|personas)', text)
        if match:
            total = int(match.group(1))
        return total

    def _parse_engagement_text(self, text: str) -> tuple[int, int]:
        """Extrae comentarios y compartidos de la cadena de interacciones."""
        comentarios = 0
        compartidos = 0
        text = text.replace('.', '').replace(',', '')

        comment_match = re.search(r'(\d+) comentario[s]?', text)
        share_match = re.search(r'(\d+) (vez |veces )?compartido[s]?', text)

        if comment_match:
            comentarios = int(comment_match.group(1))
        if share_match:
            compartidos = int(share_match.group(1))
        
        return comentarios, compartidos

    async def scrape_posts(self, max_posts: int = 30) -> FacebookScrapeResult:
        """
        Inicia el proceso de scraping de publicaciones para el perfil.
        Retorna un objeto FacebookScrapeResult.
        """
        self._setup_driver()
        
        scrape_status = "Fallido"
        error_message = None
        scraped_posts_for_result: List[FacebookPost] = [] # Posts recopilados en esta sesión
        
        # Para el upsert, usaremos la URL de la publicación
        # No necesitamos un `seen_post_urls` aquí porque MongoDB se encargará de la deduplicación
        # Pero podemos usarlo para evitar procesar el mismo elemento de DOM varias veces si se repite.
        dom_seen_post_urls = set()

        try:
            if not self._load_cookies():
                logging.error("Failed to load cookies. Scraping cannot proceed without valid session.")
                raise Exception("Cookies invalid or missing. Cannot proceed with scraping.")
            
            if not self._login_if_necessary():
                logging.error("Failed to establish a valid Facebook session. Check cookies or perform manual login.")
                raise Exception("Login failed. Cannot proceed with scraping.")

            self.driver.get(self.profile_url)
            logging.info(f"Navigating to profile: {self.profile_url}")
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='article']"))
            )
            time.sleep(random.uniform(5.0, 10.0))

            SCROLL_PAUSE_TIME = 3
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            posts_processed_count = 0

            while posts_processed_count < max_posts:
                logging.info(f"Scrolling to load more posts... (Currently {posts_processed_count}/{max_posts} scraped)")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(SCROLL_PAUSE_TIME)

                try:
                    ver_mas_buttons = self.driver.find_elements(By.XPATH, '//div[contains(text(), "Ver más") or contains(text(), "See more")]')
                    for btn in ver_mas_buttons:
                        if btn.is_displayed():
                            try:
                                self.actions.move_to_element(btn).click().perform()
                                logging.info("Clicked 'Ver más' button.")
                                time.sleep(random.uniform(1.0, 2.0))
                            except Exception as e:
                                logging.debug(f"Could not click 'Ver más' button: {e}")
                                continue
                except Exception as e:
                    logging.debug(f"No 'Ver más' buttons found or error checking them: {e}")

                candidate_posts = self.driver.find_elements(By.XPATH, '//div[@role="article"]')
                
                for post_element in candidate_posts:
                    # Intentar obtener la URL para la deduplicación *durante esta sesión*
                    current_post_url = None
                    try:
                        link_elem_for_url = post_element.find_element(By.XPATH, ".//a[contains(@href, '/posts/') or contains(@href, '/videos/') or contains(@href, '/photos/')][contains(@aria-label, '·')]")
                        current_post_url = link_elem_for_url.get_attribute("href")
                    except NoSuchElementException:
                        pass # Si no hay URL, no podemos deducir en esta sesión.

                    if current_post_url and current_post_url in dom_seen_post_urls:
                        logging.debug(f"Skipping DOM element as its URL ({current_post_url}) has already been processed in this session.")
                        continue # Ya procesado, saltar

                    try:
                        logging.info(f"Attempting to extract details for a potentially new post from DOM.")
                        post_obj = self._extract_post_details(post_element)
                        
                        if post_obj:
                            # Añadir la URL al conjunto de URLs vistas en esta sesión
                            if post_obj.url_publicacion: # Si _extract_post_details encontró una URL
                                dom_seen_post_urls.add(post_obj.url_publicacion)

                            # --- LÓGICA DE UPSERT PARA MONGODB ---
                            # Buscar por url_publicacion para decidir si actualizar o insertar
                            filter_query = {"url_publicacion": post_obj.url_publicacion}
                            # $set actualiza los campos, $setOnInsert define campos solo si es una nueva inserción
                            update_operation = {
                                "$set": post_obj.dict(by_alias=True, exclude={"_id", "id_publicacion"}), # Excluir _id y id_publicacion (UUID) del $set directo
                                "$setOnInsert": {
                                    "_id": post_obj.id_publicacion, # Usar el UUID generado para el _id
                                    "id_publicacion": post_obj.id_publicacion # Guardar el UUID también como id_publicacion
                                }
                            }
                            # `upsert=True` inserta el documento si no se encuentra el filtro
                            result = await self.posts_collection.update_one(filter_query, update_operation, upsert=True)

                            if result.upserted_id:
                                logging.info(f"✓ Inserted new post with URL: {post_obj.url_publicacion} (MongoDB _id: {result.upserted_id})")
                            elif result.modified_count > 0:
                                logging.info(f"✓ Updated existing post with URL: {post_obj.url_publicacion}")
                            else:
                                logging.info(f"✓ Post with URL: {post_obj.url_publicacion} already up-to-date or no changes detected.")
                            
                            scraped_posts_for_result.append(post_obj)
                            posts_processed_count += 1
                            
                            if posts_processed_count >= max_posts:
                                break
                        else:
                            logging.warning("Skipping post as _extract_post_details returned None (e.g., no URL found).")

                    except Exception as e:
                        logging.warning(f"Skipping a post due to error during processing or DB upsert: {e}", exc_info=True)
                        continue

                if posts_processed_count >= max_posts:
                    break

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logging.info("Reached end of scrollable content or no more posts loaded.")
                    break
                last_height = new_height
            
            scrape_status = "Completado"
            logging.info(f"Finished scraping for profile {self.profile_id}. Total posts scraped: {len(scraped_posts_for_result)}")

        except Exception as e:
            scrape_status = "Fallido"
            error_message = str(e)
            logging.error(f"Error during scraping process for {self.profile_id}: {e}", exc_info=True)
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver closed.")

        # Crear el objeto FacebookScrapeResult con las publicaciones que fueron *procesadas*
        scrape_result = FacebookScrapeResult(
            target_url_o_id=self.profile_url,
            nombre_target=self.profile_id,
            fecha_scrape=datetime.utcnow(),
            total_publicaciones_recopiladas=len(scraped_posts_for_result),
            publicaciones=scraped_posts_for_result, # Lista de objetos FacebookPost extraídos en esta sesión
            rango_fechas_busqueda=f"Últimos {len(scraped_posts_for_result)} posts disponibles o hasta el límite de {max_posts}",
            estado_scrape=scrape_status,
            mensaje_error=error_message
        )

        try:
            self.scrape_results_collection.insert_one(scrape_result.dict(by_alias=True)) 
            logging.info(f"✔ Scrape session result saved to DB for {self.profile_id}.")
        except Exception as e:
            logging.error(f"Error saving FacebookScrapeResult to DB for {self.profile_id}: {e}", exc_info=True)
        
        return scrape_result