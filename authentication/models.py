# authentication/models.py
from django.db import models
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
# Ya no necesitamos settings porque no usaremos AUTH_USER_MODEL directamente

class PasswordResetToken(models.Model):
    

    # Añadimos los campos para la relación genérica
    # Esto nos permitirá asociar el token con un Cliente o un CustomUser
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
   

    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        # Intentamos obtener el correo, que es el campo común
        user_identifier = getattr(self.content_object, 'email', None) or getattr(self.content_object, 'correo', self.object_id)
        return f"Token para {user_identifier}"