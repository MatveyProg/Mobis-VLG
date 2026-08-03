from django.contrib import admin
from django.urls import reverse


def reports_admin_link():
    """Add reports to admin index via custom template override if needed."""
    return reverse('reports:index')


# Ensure empty admin module does not break
