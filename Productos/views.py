# backend_api/Productos/views.py

from rest_framework import generics, permissions, status, filters, mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Marca
from rest_framework.exceptions import ValidationError
from rest_framework import viewsets
from .serializers import MarcaSerializer
from Ventas.models import DetalleVenta
from Compras.models import ItemCompra
from Pedidos.models import DetallePedido
from django.db.models import ProtectedError, Q, F
from .models import CategoriaProducto, Producto
from rest_framework.permissions import IsAuthenticated
from .serializers import CategoriaProductoSerializer, ProductoSerializer, ProductoDashboardStockSerializer, MarcaSerializer
from rest_framework.permissions import AllowAny
from Roles_Permisos.permissions import HasPrivilege
from rest_framework.pagination import PageNumberPagination
from Roles_Permisos.permissions import HasPrivilege, IsAdminOrReadOnly 
from rest_framework.permissions import IsAuthenticated
from Stock.serializers import BajaDeStockCreateSerializer
from rest_framework.decorators import action


class CatalogoPagination(PageNumberPagination):
    page_size = 10  # Número de productos por página.
    page_size_query_param = 'page_size'
    max_page_size = 50


class CatalogoPublicoView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductoSerializer

    
    def get_pagination_class(self):
        """
        Devuelve la clase de paginación a usar.
        Si el parámetro 'all' está en la URL, no se pagina (devuelve None).
        """
        # Verificamos si en la URL viene "?all=true" o similar.
        if self.request.query_params.get('all', '').lower() == 'true':
            # Al devolver None, Django REST Framework desactiva la paginación.
            return None 
        
        # Si no viene el parámetro, usamos la paginación normal para el móvil.
        return CatalogoPagination


    def get_queryset(self):
        """
        Este método ahora contiene toda la lógica de filtrado.
        """
        query = self.request.query_params.get('q', None)
        category_id = self.request.query_params.get('category', None)

        queryset = Producto.objects.filter(
            Q(activo=True) & 
            Q(precio_venta__gt=0) & 
            (Q(categoria__activo=True) | Q(categoria__isnull=True)) &
            (Q(marca__activo=True) | Q(marca__isnull=True))
        ).select_related('categoria', 'marca').order_by('nombre')

        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query) |
                Q(descripcion__icontains=query) |
                Q(marca__nombre__icontains=query) |
                Q(categoria__nombre__icontains=query)
            )
        
        if category_id:
            try:
                queryset = queryset.filter(categoria_id=int(category_id))
            except (ValueError, TypeError):
                pass
        
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Sobrescribimos el método `list` para añadir las categorías a la respuesta,
        manejando correctamente tanto las respuestas paginadas como las no paginadas.
        """
        # 1. Obtenemos la respuesta base de la clase padre
        response = super().list(request, *args, **kwargs)
        
        # 2. Obtenemos los datos de las categorías
        categorias_activas = CategoriaProducto.objects.filter(activo=True).order_by('nombre')
        categorias_data = CategoriaProductoSerializer(categorias_activas, many=True).data

        # 3. Verificamos si la respuesta está paginada (es un diccionario) o no (es una lista)
        if isinstance(response.data, dict):
            # CASO PAGINADO (MÓVIL): `response.data` es un diccionario.
            # Lo modificamos directamente.
            response.data['products'] = response.data.pop('results')
            response.data['categories'] = categorias_data
            return response
        else:
            # CASO NO PAGINADO (WEB con ?all=true): `response.data` es una lista.
            # Construimos un nuevo diccionario desde cero.
            final_data = {
                'products': response.data,
                'categories': categorias_data
            }
            return Response(final_data)

class CatalogoClienteView(generics.ListAPIView):
    """
    Vista del catálogo para clientes logueados, no requiere privilegios de admin.
    """
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, *args, **kwargs):
      
        productos_activos = Producto.objects.filter(
            Q(activo=True) & 
            Q(precio_venta__gt=0) & 
            (Q(categoria__activo=True) | Q(categoria__isnull=True)) &
            (Q(marca__activo=True) | Q(marca__isnull=True))
        ).select_related('categoria', 'marca').order_by('nombre')



        categorias_activas = CategoriaProducto.objects.filter(activo=True).order_by('nombre')
        productos_serializer = ProductoSerializer(productos_activos, many=True)
        categorias_serializer = CategoriaProductoSerializer(categorias_activas, many=True)
        return Response({
            'products': productos_serializer.data,
            'categories': categorias_serializer.data
        }, status=status.HTTP_200_OK)

# --- VISTAS ADMINISTRATIVAS DE CATEGORÍAS ---

class CategoriaProductoListCreateView(generics.ListCreateAPIView):
    serializer_class = CategoriaProductoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    
    def get_queryset(self):
        """
        Este método ahora filtra las categorías. Si se envía el parámetro 
        `?activo=true`, solo devolverá las categorías activas.
        """
        queryset = CategoriaProducto.objects.all()
        activo_param = self.request.query_params.get('activo')
        if activo_param and activo_param.lower() == 'true':
            queryset = queryset.filter(activo=True)
        return queryset.order_by('nombre')

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'categorias_ver'
        if method == 'POST':
            return 'categorias_crear'
        return None

class CategoriaProductoRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaProductoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'categorias_ver'
        if method in ['PUT', 'PATCH']:
            return 'categorias_editar'
        if method == 'DELETE':
            return 'categorias_eliminar'
        return None
    

    def perform_destroy(self, instance):
        if instance.productos.exists():
            raise ValidationError("Esta categoría no puede ser eliminada porque tiene productos asociados. Reasígnelos primero.")
        instance.delete()

# --- VISTAS ADMINISTRATIVAS DE PRODUCTOS ---

class ProductoListCreateView(generics.ListCreateAPIView):
    queryset = Producto.objects.select_related('categoria').all().order_by('nombre')
    serializer_class = ProductoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nombre', 'marca__nombre', 'categoria__nombre']

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'productos_ver'
        if method == 'POST':
            return 'productos_crear'
        return None

    def get_queryset(self):
        queryset = Producto.objects.select_related('categoria').all()
        activo_param = self.request.query_params.get('activo')
        if activo_param and activo_param.lower() == 'true':
            queryset = queryset.filter(activo=True)
        return queryset.order_by('nombre')

class ProductoRetrieveUpdateDestroyView(mixins.RetrieveModelMixin,
                                      mixins.UpdateModelMixin,
                                      mixins.DestroyModelMixin,
                                      viewsets.GenericViewSet):
    queryset = Producto.objects.select_related('categoria', 'marca').all()
    serializer_class = ProductoSerializer
    
   
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        
        if self.action in ['retrieve']: 
            return [permissions.AllowAny()]
        
        
        return [permissions.IsAuthenticated(), IsAdminOrReadOnly(), HasPrivilege()]

    def get_required_privilege(self, method):
        if method in ['PUT', 'PATCH']:
            return 'productos_editar'
        if method == 'DELETE':
            return 'productos_eliminar'
       
        return None

    def perform_destroy(self, instance):
        if DetalleVenta.objects.filter(producto=instance).exists():
            raise ValidationError("Este producto no puede ser eliminado porque está en ventas. Desactívelo en su lugar.")
        if ItemCompra.objects.filter(producto=instance).exists():
            raise ValidationError("Este producto no puede ser eliminado porque está en compras. Desactívelo en su lugar.")
        if DetallePedido.objects.filter(producto=instance).exists():
            raise ValidationError("Este producto no puede ser eliminado porque está en pedidos. Desactívelo en su lugar.")
        instance.delete()


    @action(detail=True, methods=['post'])
    def dar_de_baja(self, request, pk=None):
        producto = self.get_object()
        serializer_data = {
            'producto_id': producto.id,
            **request.data
        }
        
        serializer = BajaDeStockCreateSerializer(data=serializer_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        read_serializer = self.get_serializer(producto)
        return Response(read_serializer.data, status=status.HTTP_200_OK)

# --- VISTA PARA EL DASHBOARD ---

class ProductosStockSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "dashboard_ver" # Quien ve el dashboard puede ver este resumen

    def get(self, request, *args, **kwargs):
        productos_para_reponer = Producto.objects.filter(
            activo=True,
            stock_actual__lte=F('stock_minimo')
        ).order_by('stock_actual')[:10]
        
        serializer = ProductoDashboardStockSerializer(productos_para_reponer, many=True)
        
        return Response({
            "productos_para_reponer": serializer.data
        })
    

class MarcaListCreateView(generics.ListCreateAPIView):
   
    serializer_class = MarcaSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

  
    def get_queryset(self):
        """
        Este método filtra las marcas. Si se envía el parámetro `?activo=true`,
        solo devolverá las marcas activas. De lo contrario, las devuelve todas.
        """
        queryset = Marca.objects.all()
        activo_param = self.request.query_params.get('activo')
        if activo_param and activo_param.lower() == 'true':
            queryset = queryset.filter(activo=True)
        return queryset.order_by('nombre')
  

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'marcas_ver'
        if method == 'POST':
            return 'marcas_crear'
        return None

class MarcaRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Marca.objects.all()
    serializer_class = MarcaSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'marcas_ver'
        if method in ['PUT', 'PATCH']:
            return 'marcas_editar'
        if method == 'DELETE':
            return 'marcas_eliminar'
        return None
        

    def perform_destroy(self, instance):
        if instance.productos.exists():
            raise ValidationError("Esta marca no puede ser eliminada porque tiene productos asociados.")
        instance.delete()
