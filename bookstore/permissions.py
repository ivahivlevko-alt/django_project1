from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrModeratorOrReadOnly(BasePermission):
    """P3: читати можуть усі, створювати — будь-який автентифікований,
    змінювати й видаляти — власник книги або член групи Moderators."""

    moderator_group = "Moderators"

    def has_permission(self, request, view):
        # Рівень view (list/create/retrieve...): читання відкрите, запис — лише автентифікованим.
        # Для аноніма False перетворюється на 401, бо перший автентифікатор має WWW-Authenticate.
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Рівень конкретної книги; DRF викликає його лише з get_object().
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if obj.owner_id is not None and obj.owner_id == user.id:
            return True
        return user.groups.filter(name=self.moderator_group).exists()
