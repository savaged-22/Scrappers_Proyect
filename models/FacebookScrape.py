from pydantic import BaseModel, Field
from typing import Optional

class FacebookPostModel(BaseModel):
    profile: str = Field(..., description="Nombre de usuario o ID del perfil de Facebook")
    texto: str = Field(..., description="Texto del post")
    fecha: str = Field(..., description="Fecha del post")
    reacciones: Optional[str] = Field(None, description="Reacciones del post (me gusta, me encanta, etc.)")
    interacciones: Optional[str] = Field(None, description="Comentarios o veces compartido")