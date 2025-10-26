from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.conf import settings

from django.contrib.auth.models import AbstractUser

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('agent', 'Agent'),
        ('admin', 'Admin'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='userprofile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    agent_status = models.BooleanField(default=False)  # True if agent is active, False otherwise

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Dish(models.Model):
    VEG_NONVEG_CHOICES = [
        ('veg', 'Vegetarian'),
        ('nonveg', 'Non-Vegetarian'),
    ]

    CATEGORY_CHOICES = [
        ('Gravy', 'Gravy'),
        ('Side Dish', 'Side Dish'),
        ('Dosa', 'Dosa'),
        ('Rotis', 'Rotis'),
        ('Rice and Noodle', 'Rice and Noodle'),
        ('Dessert', 'Dessert'),
        ('Beverages', 'Beverages'),
        ('Snacks', 'Snacks'),
        ('Grill and Tandoori', 'Grill and Tandoori'),
        ('Soup', 'Soup'),
        ('Extras', 'Extras'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='dishes/', blank=True, null=True)
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='Extras',  # Default value
    )
    veg_nonveg = models.CharField(
        max_length=6,
        choices=VEG_NONVEG_CHOICES,
        default='veg',  # Default value
    )
    preparation_time = models.DurationField(default=0)
    tags = models.ManyToManyField(Tag, related_name='dishes', blank=True)

    def __str__(self):
        return self.name



class PlacedOrder(models.Model):
    ORDER_TYPE_CHOICES = [
        ('online', 'Online'),
        ('cod', 'Cash on Delivery'),
    ]
    order_id = models.CharField(max_length=100)
    transaction_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES)
    transaction_number = models.CharField(max_length=100, blank=True, null=True)
    order_name = models.CharField(max_length=255)
    order_phonenumber = models.CharField(max_length=15)
    dish_name = models.CharField(max_length=255)
    dish_quantity = models.PositiveIntegerField()
    dish_price = models.DecimalField(max_digits=10, decimal_places=2)
    prep_status = models.CharField(max_length=50)
    ordered_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.order_id

class OrderStatus(models.Model):
    ORDER_STATUS_CHOICES = [
        ('declined', 'Declined'),
        ('preparing', 'Preparing'),
        ('out_for_delivery', 'Out for Delivery'),
    ]
    order_id = models.CharField(max_length=100)
    transaction_type = models.CharField(max_length=10, choices=PlacedOrder.ORDER_TYPE_CHOICES)
    order_name = models.CharField(max_length=255)
    order_phonenumber = models.CharField(max_length=15)
    agents = models.ManyToManyField(UserProfile, related_name='assigned_orders', blank=True, limit_choices_to={'role': 'agent'})
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES)
    bill_value = models.DecimalField(max_digits=10, decimal_places=2)
    ordered_time = models.DateTimeField(default=timezone.now)
    agent_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"Order {self.order_id} - Status {self.order_status}"