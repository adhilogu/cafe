from django.contrib import admin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import Tag
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import Dish,PlacedOrder, OrderStatus,UserProfile


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')  # Displays ID and name in the admin list view
    search_fields = ('name',)     # Adds a search bar for the 'name' field
    ordering = ('name',)          # Orders the list by name
    list_per_page = 20            # Pagination for a cleaner view


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name','veg_nonveg', 'price',  'category', 'preparation_time','is_active', 'toggle_is_active'
    )  # Removed 'toggle_veg_nonveg' from the list_display
    list_filter = ('is_active', 'category', 'tags')  # Filters for the table
    search_fields = ('name', 'description', 'category')  # Removed 'veg_nonveg'
    ordering = ('name',)  # Orders by name
    readonly_fields = ('id',)  # Makes ID read-only
    list_per_page = 20  # Pagination
    filter_horizontal = ('tags',)  # Many-to-many filter widget

    def status(self, obj):
        """
        This method returns the status as either 'Active' or 'Not Active'
        based on the is_active field in the Dish model.
        """
        return "Active" if obj.is_active else "Not Active"

    def toggle_is_active(self, obj):
        """
        Render a button to toggle the is_active status.
        Display "Active" or "Deactivate" based on the current status.
        """
        # Define the toggle URLs for activating or deactivating the dish
        active_url = reverse("admin:toggle_dish_status", args=[obj.pk, "Active"])
        inactive_url = reverse("admin:toggle_dish_status", args=[obj.pk, "Not Active"])

        # Display the button based on the current is_active status
        if obj.is_active:
            button_html = format_html(
                """
                <button
                    class="btn btn-sm btn-success"
                    onclick="event.preventDefault(); toggleStatus('{}')"
                >
                    Active
                </button>
                """,
                inactive_url
            )
        else:
            button_html = format_html(
                """
                <button
                    class="btn btn-sm btn-danger"
                    onclick="event.preventDefault(); toggleStatus('{}')"
                >
                    Deactivate
                </button>
                """,
                active_url
            )

        return format_html(
            """
            {}
            <script>
                function toggleStatus(url) {{
                    fetch(url, {{
                        method: 'POST',
                        headers: {{
                            'X-CSRFToken': '{}',
                            'Content-Type': 'application/json'
                        }}
                    }})
                    .then(response => {{
                        if (response.ok) {{
                            location.reload();
                        }} else {{
                            alert('Failed to toggle status!');
                        }}
                    }})
                    .catch(() => alert('Failed to toggle status!'));
                }}
            </script>
            """,
            button_html,
            "{{ csrf_token }}"
        )

    toggle_is_active.short_description = "Activate/Deactivate"

    @method_decorator(csrf_exempt)
    def toggle_dish_status_view(self, request, pk, new_status):
        """
        Handle AJAX requests to toggle the status of a Dish instance (Active/Inactive).
        """
        if request.method != "POST":
            return JsonResponse({"error": "Only POST requests are allowed."}, status=405)

        # Fetch the Dish object using the primary key
        dish = get_object_or_404(Dish, pk=pk)

        # Validate the new status
        if new_status not in ["Active", "Not Active"]:
            return JsonResponse({"error": "Invalid status value."}, status=400)

        # Update the status and save
        dish.is_active = new_status == "Active"
        dish.save()

        return JsonResponse({"success": True, "new_status": new_status})

    def get_urls(self):
        """
        Extend admin URLs to include a custom endpoint for toggling status.
        """
        urls = super().get_urls()
        custom_urls = [
            path(
                "toggle-status/<int:pk>/<str:new_status>/",
                self.admin_site.admin_view(self.toggle_dish_status_view),
                name="toggle_dish_status",
            ),
        ]
        return custom_urls + urls


@admin.register(PlacedOrder)
class PlacedOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'transaction_type', 'order_name', 'order_phonenumber', 'dish_name', 'dish_quantity', 'dish_price', 'prep_status', 'ordered_time')
    list_filter = ('transaction_type', 'prep_status', 'ordered_time')
    search_fields = ('order_id', 'order_name', 'dish_name')
    ordering = ('-ordered_time',)  # Order by most recent orders
    readonly_fields = ('ordered_time',)  # Make the ordered_time field read-only in the admin panel

@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'transaction_type', 'order_name', 'order_phonenumber', 'agent_name', 'order_status', 'bill_value', 'ordered_time')
    list_filter = ('order_status', 'ordered_time')
    search_fields = ('order_id', 'order_name', 'agent_name')
    ordering = ('-ordered_time',)  # Order by most recent status update
    readonly_fields = ('ordered_time',)  # Make the ordered_time field read-only in the admin panel

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'profile_image')
    search_fields = ('user__username', 'phone_number')
    list_filter = ('user',)