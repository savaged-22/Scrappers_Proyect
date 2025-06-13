import json
import os
import random
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from dotenv import load_dotenv
from twikit import Client
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from twikit import Client, errors
from models import TweetContent, TwitterScreape 
from pydantic import ValidationError 

load_dotenv()

class TwitterScraperService:
    def __init__(self,db):
        self.client = Client("en-US")
        self.db = db
        self.collection = db["tweets"]
        self.login_attempts = 0
        self.max_login_attempts = 3

    async def _login_attempt(self):
        """Intenta loguearse una vez."""
        try:
            await self.client.login(
                auth_info_1=os.getenv('TWEET_USER'),
                auth_info_2=os.getenv('TWEET_EMAIL'),
                password=os.getenv('TWEET_PASS'),
                cookies_file='cookies.json'
            )
            logging.info("Login successful.")
            self.login_attempts = 0 # Reset attempts on success
            return True
        except errors.AuthError as e:
            logging.error(f"Authentication error during login: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during login: {e}")
            return False

    async def login(self):
        """
        Gestiona el proceso de login con reintentos y backoff exponencial.
        """
        while self.login_attempts < self.max_login_attempts:
            if await self._login_attempt():
                return
            self.login_attempts += 1
            wait_time = 2 ** self.login_attempts # Exponential backoff
            logging.warning(f"Login failed. Retrying in {wait_time} seconds (attempt {self.login_attempts}/{self.max_login_attempts}).")
            await asyncio.sleep(wait_time)
        raise Exception("Failed to log in after multiple attempts.")
    
    async def tweets_by_profile(self, profile_name: str, max_tweets_per_profile: int = 100) -> List[TweetContent]:
        """
        Rastrea tweets de un perfil dado y los convierte al modelo TweetContent.
        """
        tweets_data: List[TweetContent] = []
        try:
            user = await self.client.get_user_by_screen_name(profile_name)
            if not user:
                logging.warning(f"Profile '{profile_name}' not found.")
                return []

            now = datetime.now(timezone.utc)
            one_week_ago = now - timedelta(days=7) # Criterio de filtrado actual
            
            cursor = None
            tweets_fetched_count = 0
            
            while tweets_fetched_count < max_tweets_per_profile:
                # Ajusta el count para no exceder max_tweets_per_profile en la última iteración
                count_to_fetch = min(20, max_tweets_per_profile - tweets_fetched_count)
                if count_to_fetch <= 0:
                    break

                tweets_from_twikit = await user.get_tweets(tweet_type="Tweets", count=count_to_fetch)
                if not tweets_from_twikit:
                    break # No more tweets

                for tweet_twikit in tweets_from_twikit:
                    # Pequeña pausa para simular comportamiento humano
                    await asyncio.sleep(random.uniform(0.5, 1.5)) 

                    # Convertir la fecha de string a datetime para comparación y modelo
                    created_at_dt = None
                    if tweet_twikit.created_at:
                        try:
                            created_at_dt = datetime.strptime(tweet_twikit.created_at, "%a %b %d %H:%M:%S %z %Y")
                        except ValueError:
                            logging.warning(f"Could not parse date for tweet ID {tweet_twikit.id} from {profile_name}: {tweet_twikit.created_at}")
                            continue # Saltar este tweet si la fecha no se puede parsear

                    # Filtrar por fecha
                    if created_at_dt and created_at_dt > one_week_ago:
                        try:
                            # Extraer hashtags y menciones
                            hashtags = [hashtag.text for hashtag in tweet_twikit.hashtags] if hasattr(tweet_twikit, 'hashtags') and tweet_twikit.hashtags else []
                            mentions = [mention.screen_name for mention in tweet_twikit.mentions] if hasattr(tweet_twikit, 'mentions') and tweet_twikit.mentions else []

                            # Crear el objeto TweetContent con los nuevos campos
                            tweets_data.append(TweetContent(
                                id_tweet=tweet_twikit.id,
                                usuario_screen_name=profile_name, # O tweet_twikit.user.screen_name si quieres el autor original del retweet
                                texto_completo=tweet_twikit.full_text,
                                fecha_creacion=created_at_dt,
                                url_tweet=f"https://twitter.com/{profile_name}/status/{tweet_twikit.id}", # Construye la URL
                                retweets=tweet_twikit.retweet_count if hasattr(tweet_twikit, 'retweet_count') else 0,
                                likes=tweet_twikit.favorite_count if hasattr(tweet_twikit, 'favorite_count') else 0,
                                replies=tweet_twikit.reply_count if hasattr(tweet_twikit, 'reply_count') else 0,
                                hashtags=hashtags,
                                menciones_usuarios=mentions,
                                es_retweet=tweet_twikit.is_retweet if hasattr(tweet_twikit, 'is_retweet') else False,
                                es_respuesta=tweet_twikit.is_reply if hasattr(tweet_twikit, 'is_reply') else False
                            ))
                        except ValidationError as ve:
                            logging.error(f"Pydantic validation error for tweet ID {tweet_twikit.id} from {profile_name}: {ve}")
                            continue # Salta este tweet si no cumple con el modelo
                        except Exception as e:
                            logging.error(f"Error processing tweet ID {tweet_twikit.id} for {profile_name}: {e}", exc_info=True)
                            continue
                    else:
                        # Si los tweets ya son más viejos que el rango, podemos dejar de paginar
                        # Esto asume que los tweets vienen ordenados cronológicamente descendente.
                        logging.info(f"Reached tweets older than one week for {profile_name}. Stopping pagination.")
                        break 
                
                tweets_fetched_count += len(tweets_from_twikit)
                # Verifica si hay un cursor para la siguiente página
                if hasattr(tweets_from_twikit, 'next_cursor') and tweets_from_twikit.next_cursor:
                    cursor = tweets_from_twikit.next_cursor
                else:
                    break # No more pages

        except errors.NotFound as e:
            logging.warning(f"Profile '{profile_name}' not found: {e}")
        except errors.TooManyRequests as e:
            logging.error(f"Rate limit hit for profile {profile_name}: {e}. Pausing for 5 minutes.")
            await asyncio.sleep(60 * 5) # Pausar 5 minutos
        except Exception as e:
            logging.error(f"Unexpected error scraping profile {profile_name}: {e}", exc_info=True)
        return tweets_data

    async def _save_scrape_data(self, scrape_doc: TwitterScreape):
        """Guarda un documento TwitterScrape en la base de datos."""
        try:
            # Insertamos el documento completo de scrape
            await self.collection.insert_one(scrape_doc.dict(by_alias=True))
            logging.info(f"✔ Saved scrape data for profile: {scrape_doc.nombre_perfil} → {scrape_doc.conteo_tweets} tweets.")
        except Exception as e:
            logging.error(f"Error saving scrape data for profile {scrape_doc.nombre_perfil}: {e}", exc_info=True)

    async def scrape_and_save_profiles(self, profiles: list[str], max_tweets_per_profile: int = 100):
        """
        Orquesta el scraping de múltiples perfiles y guarda los datos.
        """
        await self.login() # Asegurarse de que el login ocurra una vez al inicio
        
        all_scraped_tweets_overall = []
        
        # Usar asyncio.gather para ejecutar las tareas de scraping de perfiles en paralelo
        # Cada tarea ahora devolverá una lista de TweetContent
        tasks = [self.tweets_by_profile(profile, max_tweets_per_profile) for profile in profiles]
        # Devuelve los resultados o las excepciones para cada tarea
        results_per_profile = await asyncio.gather(*tasks, return_exceptions=True) 

        for i, tweets_result in enumerate(results_per_profile):
            profile = profiles[i]
            
            scrape_status = "Completado"
            error_message = None
            tweets_for_current_profile: List[TweetContent] = []

            if isinstance(tweets_result, Exception): # Si hubo una excepción para este perfil
                scrape_status = "Fallido"
                error_message = str(tweets_result)
                logging.error(f"Skipping profile {profile} due to error during scraping: {error_message}")
            else: # Si el scraping fue exitoso
                tweets_for_current_profile = tweets_result
                if not tweets_for_current_profile:
                    logging.info(f"No recent tweets found for {profile}.")
                    scrape_status = "Sin Tweets Recientes"
                else:
                    all_scraped_tweets_overall.extend(tweets_for_current_profile)

            # Crear y guardar el documento TwitterScrape para cada perfil
            try:
                twitter_scrape_doc = TwitterScreape(
                    nombre_perfil=profile,
                    tweets_recopilados=tweets_for_current_profile,
                    conteo_tweets=len(tweets_for_current_profile),
                    fecha_scrape=datetime.utcnow(),
                    rango_fechas_busqueda="Últimos 7 días", # Puedes hacer esto más dinámico si cambias el filtro
                    estado_scrape=scrape_status,
                    mensaje_error=error_message
                )
                await self._save_scrape_data(twitter_scrape_doc)
            except ValidationError as ve:
                logging.error(f"Pydantic validation error creating TwitterScrape doc for {profile}: {ve}")
            except Exception as e:
                logging.error(f"Error creating/saving TwitterScrape doc for {profile}: {e}", exc_info=True)
            
            # Una pequeña pausa entre el procesamiento de perfiles (después de guardar)
            await asyncio.sleep(random.uniform(2.0, 5.0))
                                    
        return all_scraped_tweets_overall

    async def save_scrape_profile(self, profile:str, max_tweets_per_profile: int = 100):
        """
        Rastrea y guarda un solo perfil.
        """
        await self.login()
        tweets = await self.tweets_by_profile(profile, max_tweets_per_profile)
        
        scrape_status = "Completado"
        error_message = None

        if not tweets:
            logging.info(f"No recent tweets found for {profile}.")
            scrape_status = "Sin Tweets Recientes"
        
        try:
            tweet_doc = TwitterScreape(
                nombre_perfil=profile,
                tweets_recopilados=tweets,
                conteo_tweets=len(tweets),
                fecha_scrape=datetime.utcnow(),
                rango_fechas_busqueda="Últimos 7 días",
                estado_scrape=scrape_status,
                mensaje_error=error_message
            )
            await self._save_scrape_data(tweet_doc)
        except ValidationError as ve:
            logging.error(f"Pydantic validation error creating TwitterScrape doc for {profile}: {ve}")
        except Exception as e:
            logging.error(f"Error creating/saving TwitterScrape doc for {profile}: {e}", exc_info=True)

        return tweets

    # async def tweets_by_profile(self, profile: str):
    #     await self.login()
    #     tweets_data = []
    #     try:
    #         user = await self.client.get_user_by_screen_name(profile)
    #         tweets = await user.get_tweets(tweet_type="Tweets", count=100)
    #         now = datetime.now(timezone.utc)
    #         one_week_ago = now - timedelta(days=7)

    #         for tweet in tweets:
    #             await asyncio.sleep(random.uniform(1.5, 3.0))
    #             if tweet.created_at:
    #                 try:
    #                     created_at_dt = datetime.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y")
    #                     if created_at_dt > one_week_ago:
    #                         tweets_data.append(TweetContent(
    #                             usuario=profile,
    #                             fecha=created_at_dt.date().isoformat(),
    #                             tweet=tweet.full_text
    #                         ))
    #                 except ValueError:
    #                     continue
    #     except Exception as e:
    #         print(f"Error with {profile}: {e}")
    #     return tweets_data

    # async def scrape_and_save_profiles(self, profiles: list[str]):
    #     tweets_list = []
    #     for profile in profiles:
    #         tweets = await self.tweets_by_profile(profile)
    #         if tweets:
    #             tweet_doc = TwitterScreape(
    #                 profile=profile,
    #                 posts=tweets,
    #                 Rt=str(len(tweets)),
    #                 scrape_date=datetime.utcnow()
    #             )
    #             tweets_list.extend(tweets)
    #             self.collection.insert_one(tweet_doc.dict(by_alias=True))
    #             print(f"✔ Guardado: {profile} → {len(tweets)} tweets")
    #             await asyncio.sleep(random.uniform(8.0, 15.0))
                                    
    #     return tweets_list

    # async def save_scrape_profile(self, profile:str):
    #     tweets = await self.tweets_by_profile(profile)
    #     if tweets:
    #             tweet_doc = TwitterScreape(
    #                 profile=profile,
    #                 posts=tweets,
    #                 Rt=str(len(tweets)),
    #                 scrape_date=datetime.utcnow()
    #             )
    #             self.collection.insert_one(tweet_doc.dict(by_alias=True))
    #             print(f"✔ Guardado: {profile} → {len(tweets)} tweets")

    #     return tweets

    # async def tweets_profiles(profiles:list,self):
    #     todos_los_tweets = []
    #     for username in profiles:
    #         if username.strip():
    #             tweets = await self.tweets_by_profile(username)
    #             todos_los_tweets.extend(tweets)
    #             await asyncio.sleep(random.uniform(8.0, 15.0))

    #     print(f"Total de tweets guardados: {len(todos_los_tweets)}")
    #     with open("tweets_recientes.json", "w", encoding="utf-8") as jsonfile:
    #         json.dump(todos_los_tweets, jsonfile, indent=2, ensure_ascii=False)

    #     return todos_los_tweets  # <- si quieres seguir trabajando con ellos luego

   