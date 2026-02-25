from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'stripe_customer_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'username', 'stripe_customer_id')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'stripe_customer_id')

    fieldsets = UserAdmin.fieldsets + (
        ('Billing', {'fields': ('stripe_customer_id',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
