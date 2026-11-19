from rest_framework import serializers

from .models import Author, Book


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]


class BookSerializer(serializers.ModelSerializer):
    # I1: на читання author — вкладений об'єкт {"id", "name"}, на запис приймаємо author_id
    author = AuthorSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.all(), source="author", write_only=True
    )
    # owner віддаємо ім'ям користувача (str(user)); для книг без власника буде null
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Book
        fields = ["id", "title", "author", "author_id", "price", "cover", "owner"]
        read_only_fields = ["cover"]
