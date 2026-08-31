from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import CartItem
from .permissions import IsCartOwner
from .serializers import CartItemSerializer, CartSerializer
from .services import get_current_cart


class CartDetailView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        return get_current_cart(self.request)


class CartItemListCreateView(generics.ListCreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsCartOwner]
    pagination_class = None

    def get_queryset(self):
        return CartItem.objects.filter(cart=get_current_cart(self.request))

    def get_object(self):
        return get_current_cart(self.request)

    def perform_create(self, serializer):
        serializer.save(cart=self.get_object())


class CartItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsCartOwner]

    def get_queryset(self):
        return CartItem.objects.filter(cart=get_current_cart(self.request))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
