from django.db import models
from django.http import Http404


class OwnedQuerySet(models.QuerySet):
    """Each owned model declares OWNER_PATH, the lookup from the model to its owning user."""

    def for_user(self, user):
        return self.filter(**{self.model.OWNER_PATH: user})


def get_owned_or_404(model, user, **lookup):
    # Someone else's object and a missing object must be indistinguishable to the caller.
    try:
        return model.objects.for_user(user).get(**lookup)
    except (model.DoesNotExist, ValueError):
        raise Http404(f"{model.__name__} not found")
