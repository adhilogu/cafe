from django.contrib import admin
from .models import UserProfile, Tag, Dish, PlacedOrder, OrderStatus
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

# Inline for UserProfile to allow editing within User admin
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profiles'
    fields = ('phone_number', 'profile_image', 'role', 'agent_status')
    readonly_fields = ('agent_status',)

# Extend UserAdmin to include UserProfile inline
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)

# Unregister the default User admin and register with inline
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'agent_status', 'phone_number')
    list_filter = ('role', 'agent_status')
    search_fields = ('user__username', 'user__first_name', 'phone_number')
    fields = ('user', 'phone_number', 'profile_image', 'role', 'agent_status')
    readonly_fields = ('agent_status',)
    list_editable = ('role', 'phone_number')

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'veg_nonveg', 'price', 'is_active')
    list_filter = ('category', 'veg_nonveg', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('price', 'is_active')
    filter_horizontal = ('tags',)

@admin.register(PlacedOrder)
class PlacedOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'order_name','order_phonenumber','dish_name', 'dish_quantity', 'dish_price', 'prep_status', 'ordered_time')
    list_filter = ('transaction_type', 'prep_status')
    search_fields = ('order_id', 'dish_name', 'order_name', 'order_phonenumber')
    date_hierarchy = 'ordered_time'

@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'order_status', 'order_name', 'agent_list', 'agent_number', 'bill_value', 'ordered_time')
    list_filter = ('order_status', 'transaction_type')
    search_fields = ('order_id', 'order_name', 'order_phonenumber', 'agent_number')
    filter_horizontal = ('agents',)
    date_hierarchy = 'ordered_time'

    def agent_list(self, obj):
        return ", ".join([agent.user.username for agent in obj.agents.all()])
    agent_list.short_description = 'Assigned Agents'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('agents__user')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "agents":
            kwargs["queryset"] = UserProfile.objects.filter(role='agent')
        return super().formfield_for_manytomany(db_field, request, **kwargs)