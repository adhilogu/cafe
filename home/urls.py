from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('order/', views.order_page, name='order'),
    path('agent/', views.agent_page, name='agent'),
    path('order_status/', views.order_status, name='order_status'),
    path('payment/', views.payment_page , name='payment'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),
    path('profile/', views.profile_page , name='profile'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-success/', views.order_success, name='order_success'),
    path('order-failed/', views.order_failed, name='order_failed'),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

