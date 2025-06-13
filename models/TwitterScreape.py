from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import List, Optional
import uuid

class TweetContent(BaseModel):
    """
    Representa el contenido de un tweet individual raspado.
    """
    id_tweet: str = Field(..., description="ID único del tweet proporcionado por Twitter.")
    usuario_screen_name: str = Field(..., alias="usuario", description="Nombre de usuario (handle) del autor del tweet.")
    texto_completo: str = Field(..., alias="tweet", description="Contenido de texto completo del tweet.")
    fecha_creacion: datetime = Field(..., alias="fecha", description="Fecha y hora de creación del tweet en formato UTC.")
    url_tweet: Optional[HttpUrl] = Field(None, description="URL directa al tweet en Twitter.")
    retweets: int = Field(0, description="Número de retweets que ha recibido el tweet.")
    likes: int = Field(0, description="Número de 'me gusta' que ha recibido el tweet.")
    replies: int = Field(0, description="Número de respuestas al tweet.")
    hashtags: List[str] = Field([], description="Lista de hashtags presentes en el tweet.")
    menciones_usuarios: List[str] = Field([], description="Lista de nombres de usuario mencionados en el tweet.")
    es_retweet: bool = Field(False, description="Indica si el tweet es un retweet.")
    es_respuesta: bool = Field(False, description="Indica si el tweet es una respuesta a otro tweet.")
    # Puedes añadir más campos como:
    # media_urls: List[HttpUrl] = Field([], description="URLs de imágenes o videos adjuntos.")
    # id_respuesta_a: Optional[str] = Field(None, description="ID del tweet al que se está respondiendo.")

    class Config:
        populate_by_name = True # Permite usar el alias en el constructor y exportar con el nombre original

class TwitterScreape(BaseModel):
    """
    Representa una operación de raspado de Twitter para un perfil específico.
    """
    id_scrape: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id", description="ID único para esta operación de scrape.")
    nombre_perfil: str = Field(..., alias="profile", description="Nombre de usuario del perfil de Twitter raspado.")
    tweets_recopilados: List[TweetContent] = Field([], alias="posts", description="Lista de objetos TweetContent raspados del perfil.")
    conteo_tweets: int = Field(0, alias="Rt", description="Número total de tweets recopilados en esta operación.")
    fecha_scrape: datetime = Field(default_factory=datetime.utcnow, description="Fecha y hora UTC en que se realizó este scrape.")
    rango_fechas_busqueda: Optional[str] = Field(None, description="Rango de fechas de los tweets buscados (ej. 'últimos 7 días').")
    estado_scrape: str = Field("Completado", description="Estado de la operación de scrape (ej. 'Completado', 'Fallido', 'Parcial').")
    mensaje_error: Optional[str] = Field(None, description="Detalles del error si el scrape falló o fue parcial.")

    class Config:
        populate_by_name = True