from rest_framework import filters, permissions, viewsets

from .models import Author, Book
from .permissions import IsOwnerOrModeratorOrReadOnly
from .serializers import AuthorSerializer, BookSerializer


class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    """Публічний довідник авторів: читати може будь-хто. Не змінюйте права тут."""

    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [permissions.AllowAny]


class BookViewSet(viewsets.ModelViewSet):
    # select_related: author і owner підтягуються тим самим запитом, без N+1
    queryset = Book.objects.select_related("author", "owner")
    serializer_class = BookSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "author__name"]
    ordering_fields = ["price", "title"]
    permission_classes = [IsOwnerOrModeratorOrReadOnly]

    def perform_create(self, serializer):
        owner = self.request.user if self.request.user.is_authenticated else None
        serializer.save(owner=owner)
