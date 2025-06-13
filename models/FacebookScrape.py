from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import List, Optional, Literal
import uuid

# --- Sub-objeto para el contenido multimedia (imágenes, videos) ---
class MediaContent(BaseModel):
    """
    Representa un elemento multimedia (imagen o video) dentro de una publicación de Facebook.
    """
    id_media: str = Field(..., description="ID único del archivo multimedia (si aplica).")
    tipo: Literal["imagen", "video"] = Field(..., description="Tipo de contenido multimedia.")
    url: HttpUrl = Field(..., description="URL directa al archivo multimedia.")
    descripcion: Optional[str] = Field(None, description="Descripción o texto alternativo del multimedia.")
    # Para videos, podríamos añadir:
    # url_miniatura: Optional[HttpUrl] = Field(None, description="URL de la miniatura del video.")
    # duracion_segundos: Optional[int] = Field(None, description="Duración del video en segundos.")

# --- Sub-objeto para las interacciones (reacciones, comentarios, shares) ---
class EngagementMetrics(BaseModel):
    """
    Métricas de interacción para una publicación.
    """
    reacciones_totales: int = Field(0, description="Número total de reacciones (Me gusta, Me encanta, etc.).")
    comentarios_totales: int = Field(0, description="Número total de comentarios.")
    compartidos_totales: int = Field(0, description="Número total de veces que la publicación ha sido compartida.")
   
class FacebookPost(BaseModel):
    """
    Representa una publicación individual raspada de Facebook.
    """
    id_publicacion: str = Field(..., alias="_id", description="ID único de la publicación de Facebook.")
    url_publicacion: HttpUrl = Field(..., description="URL directa a la publicación en Facebook.")
    id_pagina_o_usuario: str = Field(..., description="ID de la página o usuario que publicó.")
    nombre_pagina_o_usuario: str = Field(..., description="Nombre de la página o usuario que publicó.")
    fecha_publicacion: datetime = Field(..., description="Fecha y hora UTC de la publicación.")
    contenido_texto: Optional[str] = Field(None, description="El texto principal de la publicación.")
    tipo_publicacion: Literal["estado", "foto", "video", "enlace", "evento", "otro"] = Field(
        "estado", description="Tipo de publicación (estado, foto, video, enlace, etc.)."
    )
    multimedia: List[MediaContent] = Field([], description="Lista de imágenes o videos adjuntos a la publicación.")
    enlace_adjunto: Optional[HttpUrl] = Field(None, description="URL de un enlace externo compartido en la publicación.")
    titulo_enlace: Optional[str] = Field(None, description="Título del enlace externo (si aplica).")
    descripcion_enlace: Optional[str] = Field(None, description="Descripción del enlace externo (si aplica).")
    engagement_metrics: EngagementMetrics = Field(..., description="Métricas de interacción de la publicación.")
   
    class Config:
        populate_by_name = True # Permite usar el alias _id en el constructor


class FacebookScrapeResult(BaseModel):
    """
    Representa el resultado de una operación de raspado de Facebook para una página/grupo/perfil.
    """
    id_resultado_scrape: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id", description="ID único para este resultado de scrape.")
    target_url_o_id: str = Field(..., description="URL o ID de la página/grupo/perfil raspado.")
    nombre_target: str = Field(..., description="Nombre de la página/grupo/perfil raspado.")
    fecha_scrape: datetime = Field(default_factory=datetime.utcnow, description="Fecha y hora UTC en que se realizó este scrape.")
    total_publicaciones_recopiladas: int = Field(0, description="Número total de publicaciones recopiladas en esta operación.")
    publicaciones: List[FacebookPost] = Field([], description="Lista de publicaciones de Facebook recopiladas.")
    rango_fechas_busqueda: Optional[str] = Field(None, description="Rango de fechas de las publicaciones buscadas (ej. 'últimos 30 días').")
    estado_scrape: str = Field("Completado", description="Estado de la operación de scrape (ej. 'Completado', 'Fallido', 'Parcial').")
    mensaje_error: Optional[str] = Field(None, description="Detalles del error si el scrape falló o fue parcial.")

    class Config:
        populate_by_name = True